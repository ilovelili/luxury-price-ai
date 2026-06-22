from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from typing import Any

import httpx
from fastapi import UploadFile

from luxury_price_ai.config import Settings
from luxury_price_ai.models import BrandCandidate, ImageInspectionResponse, ModelCandidate


MAX_IMAGES = 12
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
RECOMMENDED_PHOTO_ANGLES = [
    "正面全体",
    "背面全体",
    "ロゴ・刻印・ブランド表示",
    "四つ角・底面・フチ",
    "金具・ファスナー・チェーン",
    "内側・シリアル/刻印・ダメージ箇所",
]


class VisionConfigError(RuntimeError):
    pass


class VisionInputError(ValueError):
    pass


@dataclass(frozen=True)
class ImagePayload:
    filename: str
    content_type: str
    content: bytes


def inspect_luxury_images(images: list[UploadFile], settings: Settings) -> ImageInspectionResponse:
    return inspect_luxury_image_payloads(upload_files_to_payloads(images), settings)


def inspect_luxury_image_payloads(
    images: list[ImagePayload],
    settings: Settings,
) -> ImageInspectionResponse:
    if not settings.openai_api_key:
        raise VisionConfigError("OPENAI_API_KEY is required for image inspection")

    image_inputs = prepare_image_inputs(images)
    prompt = image_inspection_prompt()
    openai_inspection = inspect_with_openai(image_inputs, prompt, settings)
    if not settings.gemini_api_key:
        return openai_inspection

    try:
        gemini_inspection = inspect_with_gemini(images, prompt, settings)
    except Exception as exc:
        openai_inspection.warnings.append(f"Gemini画像解析は失敗しました: {exc}")
        return openai_inspection

    return merge_provider_inspections(openai_inspection, gemini_inspection)


def inspect_with_openai(
    image_inputs: list[dict[str, str]],
    prompt: str,
    settings: Settings,
) -> ImageInspectionResponse:
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


def inspect_with_gemini(
    images: list[ImagePayload],
    prompt: str,
    settings: Settings,
) -> ImageInspectionResponse:
    parts: list[dict[str, Any]] = [{"text": prompt}]
    for image in images:
        content_type = image.content_type or "image/jpeg"
        encoded = base64.b64encode(image.content).decode("ascii")
        parts.append(
            {
                "inline_data": {
                    "mime_type": content_type,
                    "data": encoded,
                }
            }
        )

    payload = {
        "contents": [
            {
                "parts": parts,
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_vision_model}:generateContent"
    with httpx.Client(timeout=60) as client:
        response = client.post(
            url,
            headers={
                "x-goog-api-key": settings.gemini_api_key or "",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini vision request failed: {response.status_code} {response.text[:500]}")

    return parse_gemini_inspection_response(response.json())


def merge_provider_inspections(
    openai_inspection: ImageInspectionResponse,
    gemini_inspection: ImageInspectionResponse,
) -> ImageInspectionResponse:
    model_candidates = consensus_model_candidates(
        openai_inspection.model_candidates,
        gemini_inspection.model_candidates,
    )
    if not model_candidates:
        model_candidates = sorted(
            [*openai_inspection.model_candidates, *gemini_inspection.model_candidates],
            key=lambda item: item.confidence,
            reverse=True,
        )[:5]

    warnings = dedupe_strings(
        [
            "OpenAIとGeminiの画像解析結果を統合しています。モデル/ラインは合意または候補として扱い、最終確認が必要です。",
            *openai_inspection.warnings,
            *gemini_inspection.warnings,
        ]
    )
    return ImageInspectionResponse(
        brand_candidates=merge_brand_candidates(
            openai_inspection.brand_candidates,
            gemini_inspection.brand_candidates,
        ),
        model_candidates=model_candidates[:5],
        condition_status=merge_condition_status(openai_inspection, gemini_inspection),
        condition_confidence=round(
            (openai_inspection.condition_confidence + gemini_inspection.condition_confidence) / 2,
            2,
        ),
        visible_signals=dedupe_strings(
            [*openai_inspection.visible_signals, *gemini_inspection.visible_signals]
        )[:12],
        missing_photo_angles=dedupe_strings(
            [*openai_inspection.missing_photo_angles, *gemini_inspection.missing_photo_angles]
        )[:8],
        warnings=warnings,
    )


def merge_brand_candidates(
    openai_candidates: list[BrandCandidate],
    gemini_candidates: list[BrandCandidate],
) -> list[BrandCandidate]:
    merged: dict[str, BrandCandidate] = {}
    for candidate in [*openai_candidates, *gemini_candidates]:
        key = candidate.brand.strip().upper()
        existing = merged.get(key)
        if not existing:
            merged[key] = candidate
            continue
        merged[key] = BrandCandidate(
            brand=existing.brand,
            confidence=min(1.0, max(existing.confidence, candidate.confidence) + 0.1),
            evidence=" / ".join(dedupe_strings([existing.evidence, candidate.evidence])),
        )
    return sorted(merged.values(), key=lambda item: item.confidence, reverse=True)[:5]


def consensus_model_candidates(
    openai_candidates: list[ModelCandidate],
    gemini_candidates: list[ModelCandidate],
) -> list[ModelCandidate]:
    results = []
    for openai_candidate in openai_candidates:
        openai_key = canonical_model_line(openai_candidate.model)
        if not openai_key:
            continue
        for gemini_candidate in gemini_candidates:
            gemini_key = canonical_model_line(gemini_candidate.model)
            if openai_key != gemini_key:
                continue
            confidence = min(
                1.0,
                ((openai_candidate.confidence + gemini_candidate.confidence) / 2) + 0.15,
            )
            results.append(
                ModelCandidate(
                    brand=openai_candidate.brand or gemini_candidate.brand,
                    model=openai_key,
                    confidence=round(confidence, 2),
                    evidence=(
                        f"OpenAI: {openai_candidate.evidence} / "
                        f"Gemini: {gemini_candidate.evidence}"
                    ),
                    distinguishing_features=dedupe_strings(
                        [
                            *openai_candidate.distinguishing_features,
                            *gemini_candidate.distinguishing_features,
                        ]
                    )[:10],
                )
            )
    return sorted(results, key=lambda item: item.confidence, reverse=True)


def canonical_model_line(value: str | None) -> str | None:
    text = (value or "").upper().replace("-", " ").replace("_", " ")
    japanese_text = value or ""
    is_chanel = "CHANEL" in text or "シャネル" in japanese_text
    if (is_chanel and "22" in text) or "CHANEL 22" in text:
        return "CHANEL 22"
    if (is_chanel and "19" in text) or "CHANEL 19" in text:
        return "CHANEL 19"
    if (is_chanel and "BOY" in text) or "ボーイ" in japanese_text:
        return "CHANEL Boy"
    if "COCO HANDLE" in text or "ココハンドル" in japanese_text:
        return "CHANEL Coco Handle"
    if "DOUBLE FLAP" in text or "ダブルフラップ" in japanese_text:
        return "CHANEL Classic Double Flap"
    if "CLASSIC FLAP" in text or "マトラッセ" in japanese_text:
        return "CHANEL Classic Flap"
    return None


def merge_condition_status(
    openai_inspection: ImageInspectionResponse,
    gemini_inspection: ImageInspectionResponse,
) -> str:
    if openai_inspection.condition_status == gemini_inspection.condition_status:
        return openai_inspection.condition_status
    if openai_inspection.condition_confidence >= gemini_inspection.condition_confidence:
        return openai_inspection.condition_status
    return gemini_inspection.condition_status


def upload_files_to_payloads(images: list[UploadFile]) -> list[ImagePayload]:
    payloads = []
    for image in images:
        if not image.filename and not image.content_type:
            continue
        content = image.file.read()
        image.file.seek(0)
        payloads.append(
            ImagePayload(
                filename=image.filename or "image",
                content_type=image.content_type or "",
                content=content,
            )
        )
    return payloads


def prepare_image_inputs(images: list[ImagePayload]) -> list[dict[str, str]]:
    valid_images = [
        image
        for image in images
        if image.filename or image.content_type or image.content
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

        content = image.content
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

Infer likely brand, product line/model, and visible condition status from the images. Use only visible evidence. Do not claim authenticity or final appraisal certainty. Prioritize product identification over price estimation.

For model_candidates, identify likely luxury resale model/line names such as CHANEL Classic Flap, CHANEL Boy, CHANEL 19, CHANEL Gabrielle, CHANEL Matelasse, LOUIS VUITTON Neverfull, HERMES Kelly, HERMES Birkin, etc. Include exact SKU/reference only when it is visibly readable. If exact SKU/reference is not visible, use the closest known line/model name and mention that the exact SKU needs serial/reference or measurements.

In distinguishing_features, include visible appraisal-defining attributes whenever possible: material, color, hardware color, size/class, series/era clues, strap type, closure type, and accessories. These fields are used only to help staff identify the item; do not imply the market price can be determined from images alone.

Preferred photo set is 6 images/angles:
{chr(10).join(f"- {angle}" for angle in RECOMMENDED_PHOTO_ANGLES)}

Use missing_photo_angles to list important missing angles from that set, preferably in Japanese. Do not require all angles for a result, but lower confidence when key angles are missing.

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


def parse_gemini_inspection_response(payload: dict[str, Any]) -> ImageInspectionResponse:
    text = extract_gemini_output_text(payload).strip()
    return parse_inspection_data(json.loads(strip_json_fences(text)))


def parse_inspection_data(data: dict[str, Any]) -> ImageInspectionResponse:
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


def extract_gemini_output_text(payload: dict[str, Any]) -> str:
    chunks = []
    for candidate in payload.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        for part in content.get("parts", []):
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    if not chunks:
        raise RuntimeError("Gemini response did not contain output text")
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


def dedupe_strings(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
