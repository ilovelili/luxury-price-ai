from __future__ import annotations

import re

from luxury_price_ai.models import PriceEstimateRequest


RANK_RE = re.compile(r"(?<![A-Z0-9])(SA|AB|BC|S|A|B|C|D|F)(?![A-Z0-9])", re.IGNORECASE)

SHAPE_KEYWORDS = [
    ("チェーンウォレット", "チェーンウォレット"),
    ("チェーンショルダー", "ショルダーバッグ"),
    ("ショルダー", "ショルダーバッグ"),
    ("ハンドバッグ", "ハンドバッグ"),
    ("ハンド", "ハンドバッグ"),
    ("トート", "トートバッグ"),
    ("バニティ", "バニティバッグ"),
    ("リュック", "リュック"),
    ("バックパック", "リュック"),
    ("財布", "財布"),
    ("ウォレット", "財布"),
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


def infer_brand(text: str) -> str:
    upper = text.upper()
    if "CHANEL" in upper or "シャネル" in text:
        return "CHANEL"
    # MVP data is currently CHANEL-focused. Keep the estimator usable while the
    # intake UX stays natural-language only.
    return "CHANEL"


def infer_category(text: str) -> str | None:
    if any(word in text for word in BAG_WORDS):
        return "バッグ"
    return None


def infer_shape(text: str) -> str | None:
    for keyword, shape in SHAPE_KEYWORDS:
        if keyword in text:
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
