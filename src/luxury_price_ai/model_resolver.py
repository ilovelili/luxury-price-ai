from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any

import httpx

from luxury_price_ai.config import Settings
from luxury_price_ai.models import AuctionSale, ImageInspectionResponse
from luxury_price_ai.tokens import WORD_RE, extract_tokens, normalize_text


GENERIC_TITLE_TERMS = {
    "CHANEL",
    "シャネル",
    "LOUIS",
    "VUITTON",
    "LOUISVUITTON",
    "ルイヴィトン",
    "HERMES",
    "エルメス",
    "GUCCI",
    "グッチ",
    "PRADA",
    "プラダ",
    "DIOR",
    "ディオール",
    "バッグ",
    "BAG",
    "ショルダー",
    "ショルダーバッグ",
    "ハンドバッグ",
    "トートバッグ",
    "財布",
    "ウォレット",
}


def resolve_database_terms_for_inspection(
    *,
    inspection: ImageInspectionResponse,
    candidates: list[AuctionSale],
    settings: Settings,
    max_terms: int = 120,
) -> list[str]:
    if not inspection.model_candidates or not candidates:
        return []
    database_terms = database_title_terms(candidates, limit=max_terms)
    if not database_terms:
        return []

    vision_text = build_vision_model_text(inspection)
    if not vision_text:
        return []

    try:
        if settings.gemini_api_key:
            return resolve_terms_with_gemini(
                vision_text=vision_text,
                database_terms=database_terms,
                settings=settings,
            )
        if settings.openai_api_key:
            return resolve_terms_with_openai(
                vision_text=vision_text,
                database_terms=database_terms,
                settings=settings,
            )
    except Exception:
        return []
    return []


def database_title_terms(candidates: list[AuctionSale], *, limit: int) -> list[str]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for sale in candidates:
        title = sale.title or ""
        tokens = extract_tokens(title)
        for term in [
            *tokens.models,
            *tokens.materials,
            *tokens.colors,
            *tokens.hardware,
            *tokens.accessories,
            *tokens.words,
            *raw_title_words(title),
        ]:
            normalized = normalize_database_term(term)
            if not normalized:
                continue
            counts[normalized] += 1
            display.setdefault(normalized, term.strip())

    ranked = sorted(
        counts,
        key=lambda item: (
            counts[item],
            min(len(display[item]), 14),
            display[item],
        ),
        reverse=True,
    )
    return [display[item] for item in ranked[:limit]]


def raw_title_words(title: str) -> list[str]:
    words = WORD_RE.findall(title)
    result: list[str] = []
    for word in words:
        cleaned = word.strip()
        if len(cleaned) < 2:
            continue
        result.append(cleaned)
    return result


def normalize_database_term(term: str) -> str:
    value = term.strip()
    if not value:
        return ""
    normalized = normalize_text(value)
    if normalized in GENERIC_TITLE_TERMS:
        return ""
    if normalized.isdigit() and normalized not in {"19", "22", "25", "30", "35", "40"}:
        return ""
    return normalized


def build_vision_model_text(inspection: ImageInspectionResponse) -> str:
    parts: list[str] = []
    for candidate in inspection.model_candidates[:5]:
        parts.extend(
            [
                candidate.brand,
                candidate.model,
                candidate.evidence,
                " ".join(candidate.distinguishing_features),
            ]
        )
    parts.extend(inspection.visible_signals)
    return "\n".join(part.strip() for part in parts if part and part.strip())


def resolve_terms_with_gemini(
    *,
    vision_text: str,
    database_terms: list[str],
    settings: Settings,
) -> list[str]:
    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_vision_model}:generateContent",
        params={"key": settings.gemini_api_key},
        json={
            "contents": [
                {
                    "parts": [
                        {
                            "text": resolver_prompt(
                                vision_text=vision_text,
                                database_terms=database_terms,
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        },
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    text = (
        payload.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    return parse_resolver_terms(text, database_terms)


def resolve_terms_with_openai(
    *,
    vision_text: str,
    database_terms: list[str],
    settings: Settings,
) -> list[str]:
    response = httpx.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.openai_vision_model,
            "input": resolver_prompt(
                vision_text=vision_text,
                database_terms=database_terms,
            ),
            "temperature": 0,
        },
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    return parse_resolver_terms(extract_openai_text(payload), database_terms)


def resolver_prompt(*, vision_text: str, database_terms: list[str]) -> str:
    return f"""You map luxury product identification text to auction database terms.

Vision/model evidence:
{vision_text}

Allowed auction database terms extracted from actual sold-item titles:
{json.dumps(database_terms, ensure_ascii=False)}

Choose only terms from the allowed auction database terms that describe the same visible model/line/material/color/hardware in the vision evidence.
Handle English/Japanese wording differences. Do not add terms that are not in the allowed list.
Do not include serial, production era, exact size, or accessories unless the vision evidence explicitly supports them.
Return JSON only:
{{"terms":["term"],"confidence":0.0,"reason":"short reason"}}
"""


def parse_resolver_terms(text: str, allowed_terms: list[str]) -> list[str]:
    if not text:
        return []
    data = json.loads(strip_json_fences(text))
    allowed_by_key = {normalize_text(term): term for term in allowed_terms}
    terms = []
    for value in data.get("terms", []):
        key = normalize_text(str(value))
        term = allowed_by_key.get(key)
        if term and term not in terms:
            terms.append(term)
    return terms[:8]


def extract_openai_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    parts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()
