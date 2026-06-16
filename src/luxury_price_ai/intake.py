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
