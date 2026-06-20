from __future__ import annotations

import math
from datetime import date

from luxury_price_ai.config import Settings
from luxury_price_ai.models import (
    AuctionSale,
    ComparableSale,
    PriceEstimateRequest,
    PriceEstimateResponse,
    PriceRange,
)
from luxury_price_ai.tokens import canonical_token, extract_tokens, normalize_text, token_set


RANK_ORDER = {
    "S": 0,
    "N": 0,
    "A": 1,
    "AB": 2,
    "B": 3,
    "BC": 4,
    "C": 5,
    "D": 6,
    "F": 7,
}


def estimate_price(
    request: PriceEstimateRequest,
    candidates: list[AuctionSale],
    settings: Settings,
) -> PriceEstimateResponse:
    request_tokens = extract_tokens(request.title)
    missing_inputs = missing_fields(request)
    scored = [
        score_sale(request, request_tokens, candidate)
        for candidate in candidates
        if candidate.price_jpy > 0
    ]
    scored.sort(key=lambda item: item.score, reverse=True)
    qualified = [
        item
        for item in scored
        if item.match_quality in {"exact", "close"}
    ]
    weak = [
        item
        for item in scored
        if item.match_quality == "weak"
    ]
    excluded = [
        item
        for item in scored
        if item.match_quality == "excluded"
    ]
    comparables = [*qualified, *weak, *excluded][: request.limit]

    market_range = price_range([item.price_jpy for item in qualified])
    offer_range = apply_offer_range(market_range, settings.offer_multiplier)
    confidence = estimate_confidence(qualified, missing_inputs)

    return PriceEstimateResponse(
        market_price_jpy=market_range,
        purchase_offer_jpy=offer_range,
        confidence=confidence,
        missing_inputs=missing_inputs,
        extracted_tokens=request_tokens,
        comparable_count=len(scored),
        qualified_comparable_count=len(qualified),
        comparables=comparables,
    )


def score_sale(
    request: PriceEstimateRequest,
    request_tokens,
    sale: AuctionSale,
) -> ComparableSale:
    score = 0.0
    reasons = []
    exclusion_reasons = []

    if same_text(request.brand, sale.brand):
        score += 10
        reasons.append("same brand")
    else:
        exclusion_reasons.append("different brand")

    if request.category and same_text(request.category, sale.category):
        score += 8
        reasons.append("same category")
    elif request.category:
        exclusion_reasons.append("different category")

    if request.shape and same_text(request.shape, sale.shape):
        score += 10
        reasons.append("same shape")
    elif request.shape:
        exclusion_reasons.append("different shape")

    rank_points = rank_similarity(request.rank, sale.rank)
    if rank_points:
        score += rank_points
        reasons.append(f"rank similarity +{rank_points:.1f}")

    sale_tokens = extract_tokens(sale.title)
    overlap = token_set(request_tokens) & token_set(sale_tokens)
    if overlap:
        token_points = 6 * len(overlap)
        score += token_points
        reasons.append("shared tokens: " + ", ".join(sorted(overlap)))
    exclusion_reasons.extend(required_token_mismatches(request_tokens, sale_tokens))

    title_points = title_similarity(request.title, sale.title) * 8
    if title_points:
        score += title_points
        reasons.append(f"title overlap +{title_points:.1f}")

    recency_points = recency_score(sale.sold_date)
    if recency_points:
        score += recency_points
        reasons.append(f"recent sale +{recency_points:.1f}")

    match_quality = classify_match(request, request_tokens, sale, sale_tokens, exclusion_reasons)
    if match_quality == "excluded":
        score = 0.0

    return ComparableSale(
        item_id=sale.item_id,
        sold_date=sale.sold_date,
        brand=sale.brand,
        title=sale.title,
        rank=sale.rank,
        category=sale.category,
        shape=sale.shape,
        price_jpy=sale.price_jpy,
        item_url=sale.item_url,
        image_url=sale.image_url,
        score=round(score, 3),
        match_quality=match_quality,
        score_reasons=reasons,
        exclusion_reasons=exclusion_reasons,
        extracted_tokens=sale_tokens,
    )


def required_token_mismatches(request_tokens, sale_tokens) -> list[str]:
    mismatches = []
    requirements = [
        ("model/line", request_tokens.models, sale_tokens.models),
        ("material", request_tokens.materials, sale_tokens.materials),
        ("color", request_tokens.colors, sale_tokens.colors),
        ("hardware", request_tokens.hardware, sale_tokens.hardware),
    ]
    for label, requested, actual in requirements:
        if requested and not token_overlap(requested, actual):
            mismatches.append(f"missing {label} match")
    return mismatches


def classify_match(
    request: PriceEstimateRequest,
    request_tokens,
    sale: AuctionSale,
    sale_tokens,
    exclusion_reasons: list[str],
) -> str:
    hard_mismatches = {
        "different brand",
        "different category",
        "different shape",
        "missing model/line match",
        "missing material match",
        "missing color match",
        "missing hardware match",
    }
    if any(reason in hard_mismatches for reason in exclusion_reasons):
        return "excluded"
    if not request_tokens.models:
        return "weak"
    if not request.rank or not sale.rank:
        return "weak"
    distance = rank_distance(request.rank, sale.rank)
    if distance is None:
        return "weak"
    if distance > 1:
        exclusion_reasons.append("condition rank too different")
        return "excluded"
    if distance == 0 and exact_token_match(request_tokens, sale_tokens):
        return "exact"
    return "close"


def exact_token_match(request_tokens, sale_tokens) -> bool:
    groups = [
        (request_tokens.models, sale_tokens.models),
        (request_tokens.materials, sale_tokens.materials),
        (request_tokens.colors, sale_tokens.colors),
        (request_tokens.hardware, sale_tokens.hardware),
    ]
    return all(not requested or token_overlap(requested, actual) for requested, actual in groups)


def token_overlap(left: list[str], right: list[str]) -> bool:
    return bool({canonical_token(item) for item in left} & {canonical_token(item) for item in right})


def same_text(left: str | None, right: str | None) -> bool:
    return bool(left and right and normalize_text(left) == normalize_text(right))


def rank_similarity(request_rank: str | None, sale_rank: str | None) -> float:
    if not request_rank or not sale_rank:
        return 0.0
    left = RANK_ORDER.get(normalize_text(request_rank))
    right = RANK_ORDER.get(normalize_text(sale_rank))
    if left is None or right is None:
        return 0.0
    distance = abs(left - right)
    return max(0.0, 8.0 - (distance * 2.0))


def rank_distance(request_rank: str | None, sale_rank: str | None) -> int | None:
    if not request_rank or not sale_rank:
        return None
    left = RANK_ORDER.get(normalize_text(request_rank))
    right = RANK_ORDER.get(normalize_text(sale_rank))
    if left is None or right is None:
        return None
    return abs(left - right)


def title_similarity(left: str, right: str) -> float:
    left_words = set(extract_tokens(left).words)
    right_words = set(extract_tokens(right).words)
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / len(left_words | right_words)


def recency_score(sold_date: date | None) -> float:
    if not sold_date:
        return 0.0
    days_old = max(0, (date.today() - sold_date).days)
    return max(0.0, 4.0 * math.exp(-days_old / 540.0))


def price_range(prices: list[int]) -> PriceRange | None:
    if not prices:
        return None
    sorted_prices = sorted(prices)
    return PriceRange(
        low=percentile(sorted_prices, 0.25),
        mid=percentile(sorted_prices, 0.50),
        high=percentile(sorted_prices, 0.75),
    )


def percentile(sorted_values: list[int], q: float) -> int:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]
    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    weight = position - lower
    return round(lower_value + ((upper_value - lower_value) * weight))


def apply_offer_range(market_range: PriceRange | None, multiplier: float) -> PriceRange | None:
    if not market_range:
        return None
    return PriceRange(
        low=round_to_1000(market_range.low * multiplier),
        mid=round_to_1000(market_range.mid * multiplier),
        high=round_to_1000(market_range.high * multiplier),
    )


def round_to_1000(value: float) -> int:
    return int(round(value / 1000.0) * 1000)


def missing_fields(request: PriceEstimateRequest) -> list[str]:
    missing = []
    if not request.category:
        missing.append("category")
    if not request.shape:
        missing.append("shape")
    if not request.rank:
        missing.append("rank")
    tokens = extract_tokens(request.title)
    if not tokens.models:
        missing.append("confirmed model/line")
    if not tokens.materials:
        missing.append("confirmed material")
    if not tokens.colors:
        missing.append("confirmed color")
    if not tokens.hardware:
        missing.append("confirmed hardware")
    return missing


def estimate_confidence(comparables: list[ComparableSale], missing_inputs: list[str]) -> float:
    if not comparables:
        return 0.0
    count_score = min(1.0, len(comparables) / 20.0)
    top_score = min(1.0, comparables[0].score / 45.0)
    missing_penalty = min(0.5, len(missing_inputs) * 0.1)
    return round(max(0.0, (count_score * 0.45) + (top_score * 0.55) - missing_penalty), 2)
