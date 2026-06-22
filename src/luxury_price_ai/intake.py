from __future__ import annotations

import re

from luxury_price_ai.models import AuctionAnalysisRequest, ImageInspectionResponse, PriceEstimateRequest


RANK_RE = re.compile(r"(?<![A-Z0-9])(SA|AB|BC|S|A|B|C|D|F)(?![A-Z0-9])", re.IGNORECASE)

SHAPE_KEYWORDS = [
    ("チェーンウォレット", "チェーンウォレット"),
    ("チェーンショルダー", "ショルダーバッグ"),
    ("ショルダー", "ショルダーバッグ"),
    ("SHOULDER BAG", "ショルダーバッグ"),
    ("SHOULDER", "ショルダーバッグ"),
    ("ハンドバッグ", "ハンドバッグ"),
    ("ハンド", "ハンドバッグ"),
    ("HAND BAG", "ハンドバッグ"),
    ("HANDBAG", "ハンドバッグ"),
    ("トート", "トートバッグ"),
    ("TOTE", "トートバッグ"),
    ("バニティ", "バニティバッグ"),
    ("VANITY", "バニティバッグ"),
    ("リュック", "リュック"),
    ("バックパック", "リュック"),
    ("BACKPACK", "リュック"),
    ("財布", "財布"),
    ("ウォレット", "財布"),
    ("WALLET", "財布"),
]

BAG_WORDS = {
    "バッグ",
    "ショルダー",
    "チェーンショルダー",
    "ハンドバッグ",
    "トート",
    "バニティ",
    "リュック",
    "バックパック",
}

IMAGE_SEARCH_ALIASES = [
    (
        ("CHANEL CLASSIC DOUBLE FLAP", "CLASSIC DOUBLE FLAP", "DOUBLE FLAP"),
        ["マトラッセ", "クラシックフラップ", "ダブルフラップ"],
    ),
    (
        ("CHANEL CLASSIC FLAP", "CLASSIC FLAP"),
        ["マトラッセ", "クラシックフラップ"],
    ),
    (
        ("CHANEL BOY", "BOY CHANEL"),
        ["ボーイシャネル", "ボーイ"],
    ),
    (
        ("CHANEL COCO HANDLE", "COCO HANDLE"),
        ["ココハンドル"],
    ),
    (
        ("CHANEL 22", "CHANEL22"),
        ["シャネル22"],
    ),
    (
        ("CHANEL 19", "CHANEL19"),
        ["シャネル19"],
    ),
    (
        ("CAVIAR LEATHER", "CAVIAR SKIN", "CAVIAR", "GRAINED CALFSKIN", "GRAINED LEATHER"),
        ["キャビアスキン"],
    ),
    (
        ("LAMBSKIN", "LAMB SKIN", "LAMB LEATHER"),
        ["ラムスキン"],
    ),
    (
        ("GOLD HARDWARE", "GOLD METAL", "GOLD TONE", "GOLD CHAIN", "GOLD CC"),
        ["ゴールド金具"],
    ),
    (
        ("SILVER HARDWARE", "SILVER METAL", "SILVER TONE", "SILVER CHAIN", "SILVER CC"),
        ["シルバー金具"],
    ),
    (
        ("BLACK",),
        ["ブラック"],
    ),
    (
        ("WHITE",),
        ["ホワイト"],
    ),
    (
        ("BEIGE",),
        ["ベージュ"],
    ),
]


def build_price_request_from_description(description: str, limit: int = 10) -> PriceEstimateRequest:
    text = description.strip()
    return PriceEstimateRequest(
        brand=infer_brand(text),
        category=infer_category(text),
        shape=infer_shape(text),
        rank=infer_rank(text),
        title=text,
        limit=limit,
    )


def build_price_request_from_form(
    *,
    brand: str,
    item_category: str,
    item_shape: str,
    item_name: str,
    item_color: str = "",
    condition_status: str = "",
    item_description: str = "",
    limit: int = 10,
) -> PriceEstimateRequest:
    normalized_brand = brand.strip().upper()
    normalized_category = normalize_category(item_category)
    normalized_shape = normalize_shape(item_shape)
    normalized_rank = normalize_condition_status(condition_status)
    title_parts = [
        normalized_brand,
        item_name.strip(),
        item_color.strip(),
        normalized_shape or "",
        condition_status.strip(),
        item_description.strip(),
    ]
    title = " ".join(part for part in title_parts if part)
    return PriceEstimateRequest(
        brand=normalized_brand or infer_brand(title),
        category=normalized_category,
        shape=normalized_shape,
        rank=normalized_rank,
        title=title,
        limit=limit,
    )


def build_auction_request_from_image_inspection(
    inspection: ImageInspectionResponse,
    *,
    brand: str = "",
    item_category: str = "",
    item_shape: str = "",
    item_name: str = "",
    item_color: str = "",
    condition_status: str = "",
    item_description: str = "",
    limit: int = 50,
) -> AuctionAnalysisRequest:
    inferred_brand = strongest_brand(inspection) or infer_brand(image_search_text(inspection))
    normalized_brand = brand.strip().upper()
    normalized_category = normalize_category(item_category)
    normalized_shape = normalize_shape(item_shape)
    normalized_rank = normalize_condition_status(condition_status)

    inspection_text = image_search_text(inspection)
    enriched_inspection_text = enrich_image_search_text(inspection_text)
    inferred_shape = (
        normalized_shape
        or infer_shape(item_name)
        or infer_shape(item_description)
        or infer_shape(enriched_inspection_text)
    )
    title_parts = [
        normalized_brand or inferred_brand,
        item_name.strip(),
        item_color.strip(),
        inferred_shape or "",
        item_description.strip(),
        enriched_inspection_text,
    ]
    title = " ".join(part for part in title_parts if part)
    return AuctionAnalysisRequest(
        brand=normalized_brand or inferred_brand,
        category=normalized_category or infer_category(title) or "バッグ",
        shape=inferred_shape,
        rank=normalized_rank,
        title=title,
        limit=limit,
    )


def image_analysis_missing_inputs(
    inspection: ImageInspectionResponse,
    request: AuctionAnalysisRequest,
) -> list[str]:
    missing = []
    if not request.brand or request.brand == "不明":
        missing.append("brand")
    if not request.category:
        missing.append("category")
    if not request.shape:
        missing.append("shape")
    if not request.rank:
        missing.append("condition/rank")
    if not inspection.model_candidates:
        missing.append("model/material/color details")
    for angle in inspection.missing_photo_angles:
        missing.append(f"photo: {angle}")
    return missing


def image_analysis_confidence(
    inspection: ImageInspectionResponse,
    request: AuctionAnalysisRequest,
    record_count: int,
    missing_inputs: list[str],
) -> float:
    brand_confidence = max((candidate.confidence for candidate in inspection.brand_candidates), default=0.0)
    model_confidence = max((candidate.confidence for candidate in inspection.model_candidates), default=0.0)
    condition_confidence = inspection.condition_confidence
    result_count_score = min(1.0, record_count / 20.0)
    completeness_penalty = min(0.45, len(missing_inputs) * 0.05)
    request_bonus = 0.1 if request.shape and request.rank else 0.0
    confidence = (
        (brand_confidence * 0.30)
        + (model_confidence * 0.20)
        + (condition_confidence * 0.20)
        + (result_count_score * 0.20)
        + request_bonus
        - completeness_penalty
    )
    return round(max(0.0, min(1.0, confidence)), 2)


def infer_brand(text: str) -> str:
    upper = text.upper()
    if "CHANEL" in upper or "シャネル" in text:
        return "CHANEL"
    # MVP data is currently CHANEL-focused. Keep the estimator usable while the
    # intake UX stays natural-language only.
    return "CHANEL"


def strongest_brand(inspection: ImageInspectionResponse) -> str | None:
    candidates = [
        candidate
        for candidate in inspection.brand_candidates
        if candidate.brand and candidate.brand != "不明"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate.confidence).brand.strip().upper()


def image_search_text(inspection: ImageInspectionResponse) -> str:
    parts = []
    for candidate in inspection.model_candidates:
        parts.extend(
            [
                candidate.brand,
                candidate.model,
                candidate.evidence,
                " ".join(candidate.distinguishing_features),
            ]
        )
    parts.extend(inspection.visible_signals)
    return " ".join(part.strip() for part in parts if part and part.strip())


def enrich_image_search_text(text: str) -> str:
    upper = text.upper()
    additions = []
    for aliases, terms in IMAGE_SEARCH_ALIASES:
        if any(alias in upper for alias in aliases):
            additions.extend(terms)
    return " ".join(dedupe_text_parts([text, *additions]))


def dedupe_text_parts(parts: list[str]) -> list[str]:
    seen = set()
    result = []
    for part in parts:
        value = part.strip()
        if not value:
            continue
        key = value.upper()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def infer_category(text: str) -> str | None:
    if any(word in text for word in BAG_WORDS):
        return "バッグ"
    return None


def infer_shape(text: str) -> str | None:
    normalized_text = text.upper()
    for keyword, shape in SHAPE_KEYWORDS:
        if keyword in text or keyword in normalized_text:
            return shape
    return None


def infer_rank(text: str) -> str | None:
    upper = text.upper().replace("状態", " ")
    if "未使用" in text or "新品" in text:
        return "S"
    match = RANK_RE.search(upper)
    if match:
        return match.group(1).upper()
    return None


def normalize_category(value: str) -> str | None:
    text = value.strip()
    if text in {"ブランドバッグ", "バッグ"}:
        return "バッグ"
    if text in {"財布", "時計", "アクセサリー", "服", "スニーカー・靴", "貴金属", "美術品・骨董品"}:
        return text
    return infer_category(text)


def normalize_shape(value: str) -> str | None:
    text = value.strip()
    if not text or text == "その他":
        return None
    return infer_shape(text) or text


def normalize_condition_status(value: str) -> str | None:
    text = value.strip()
    if not text or text == "不明":
        return None
    status_rank = {
        "新品・未使用": "S",
        "ほぼ新品": "A",
        "使用感少ない": "AB",
        "使用感あり": "B",
        "古い・ダメージあり": "C",
    }
    return status_rank.get(text) or infer_rank(text)
