from __future__ import annotations

import base64
import json
from typing import Any

import httpx
from fastapi import UploadFile

from luxury_price_ai.config import Settings
from luxury_price_ai.models import BrandCandidate, ImageInspectionResponse, ModelCandidate


MAX_IMAGES = 6
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_CONDITION_STATUS = {
    "新品・未使用",
    "ほぼ新品",
    "使用感少ない",
    "使用感あり",
    "古い・ダメージあり",
    "不明",
}
DEFAULT_WARNING = "画像解析は参考情報です。写真だけで真贋や最終状態を断定しません。"


class VisionConfigError(RuntimeError):
    pass


class VisionInputError(ValueError):
    pass


def inspect_luxury_images(images: list[UploadFile], settings: Settings) -> ImageInspectionResponse:
    if not settings.openai_api_key:
        raise VisionConfigError("OPENAI_API_KEY is required for image inspection")

    image_inputs = prepare_image_inputs(images)
    prompt = image_inspection_prompt()
    payload = {
        "model": settings.openai_vision_model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    *image_inputs,
                ],
            }
        ],
        "max_output_tokens": 1600,
    }

    with httpx.Client(timeout=60) as client:
        response = client.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI vision request failed: {response.status_code} {response.text[:500]}")

    return parse_inspection_response(response.json())


def prepare_image_inputs(images: list[UploadFile]) -> list[dict[str, str]]:
    valid_images = [
        image
        for image in images
        if image.filename or image.content_type
    ]
    if not valid_images:
        raise VisionInputError("画像を1枚以上アップロードしてください")
    if len(valid_images) > MAX_IMAGES:
        raise VisionInputError(f"画像は最大{MAX_IMAGES}枚までです")

    image_inputs = []
    for image in valid_images:
        content_type = image.content_type or ""
        if not content_type.startswith("image/"):
            raise VisionInputError("画像ファイルのみアップロードできます")

        content = image.file.read()
        image.file.seek(0)
        if not content:
            raise VisionInputError("空の画像ファイルは解析できません")
        if len(content) > MAX_IMAGE_BYTES:
            raise VisionInputError("画像は1枚10MB以下にしてください")

        encoded = base64.b64encode(content).decode("ascii")
        image_inputs.append(
            {
                "type": "input_image",
                "image_url": f"data:{content_type};base64,{encoded}",
            }
        )
    return image_inputs


def image_inspection_prompt() -> str:
    statuses = "、".join(sorted(ALLOWED_CONDITION_STATUS))
    return f"""You inspect uploaded photos of a luxury resale item.

Return JSON only. Do not wrap it in Markdown.

Infer likely brand, product line/model, and visible condition status from the images. Use only visible evidence. Do not claim authenticity or final appraisal certainty.

For model_candidates, identify likely luxury resale model/line names such as CHANEL Classic Flap, CHANEL Boy, CHANEL 19, CHANEL Gabrielle, CHANEL Matelasse, LOUIS VUITTON Neverfull, HERMES Kelly, HERMES Birkin, etc. Include exact SKU/reference only when it is visibly readable. If exact SKU/reference is not visible, use the closest known line/model name and mention that the exact SKU needs serial/reference or measurements.

Allowed condition_status values: {statuses}

JSON schema:
{{
  "brand_candidates": [
    {{"brand": "CHANEL", "confidence": 0.74, "evidence": "visible logo or design cue"}}
  ],
  "model_candidates": [
    {{
      "brand": "CHANEL",
      "model": "Classic Flap Medium",
      "confidence": 0.56,
      "evidence": "quilted flap, CC turn-lock, chain strap, proportions",
      "distinguishing_features": ["quilted flap", "CC turn-lock", "chain strap"]
    }}
  ],
  "condition_status": "使用感少ない",
  "condition_confidence": 0.65,
  "visible_signals": ["visible cue"],
  "missing_photo_angles": ["additional photo needed"],
  "warnings": ["do not authenticate from photos"]
}}

If brand is unclear, use brand "不明" with low confidence. If model/line is unclear, return an empty model_candidates list. If condition is unclear, use condition_status "不明".
"""


def parse_inspection_response(payload: dict[str, Any]) -> ImageInspectionResponse:
    text = extract_output_text(payload).strip()
    data = json.loads(strip_json_fences(text))

    condition_status = data.get("condition_status") or "不明"
    if condition_status not in ALLOWED_CONDITION_STATUS:
        condition_status = "不明"

    brand_candidates = [
        BrandCandidate(
            brand=str(item.get("brand") or "不明").strip() or "不明",
            confidence=coerce_confidence(item.get("confidence")),
            evidence=str(item.get("evidence") or ""),
        )
        for item in data.get("brand_candidates", [])
        if isinstance(item, dict)
    ]
    if not brand_candidates:
        brand_candidates = [
            BrandCandidate(brand="不明", confidence=0.0, evidence="画像からブランドを確認できませんでした")
        ]

    model_candidates = [
        ModelCandidate(
            brand=str(item.get("brand") or "不明").strip() or "不明",
            model=str(item.get("model") or "不明").strip() or "不明",
            confidence=coerce_confidence(item.get("confidence")),
            evidence=str(item.get("evidence") or ""),
            distinguishing_features=list_of_strings(item.get("distinguishing_features")),
        )
        for item in data.get("model_candidates", [])
        if isinstance(item, dict)
    ]

    warnings = list_of_strings(data.get("warnings"))
    if not warnings:
        warnings = [DEFAULT_WARNING]
    elif DEFAULT_WARNING not in warnings:
        warnings.append(DEFAULT_WARNING)

    return ImageInspectionResponse(
        brand_candidates=brand_candidates[:5],
        model_candidates=model_candidates[:5],
        condition_status=condition_status,
        condition_confidence=coerce_confidence(data.get("condition_confidence")),
        visible_signals=list_of_strings(data.get("visible_signals")),
        missing_photo_angles=list_of_strings(data.get("missing_photo_angles")),
        warnings=warnings,
    )


def extract_output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    chunks = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    if not chunks:
        raise RuntimeError("OpenAI response did not contain output text")
    return "\n".join(chunks)


def strip_json_fences(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def coerce_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
