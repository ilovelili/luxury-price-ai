from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class AuctionSale(BaseModel):
    item_id: str
    brand: str
    category: str | None = None
    shape: str | None = None
    rank: str | None = None
    title: str
    sold_date: date | None = None
    price_jpy: int
    item_url: str | None = None
    image_url: str | None = None
    auction: str | None = None
    source_month: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ExtractedTokens(BaseModel):
    models: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    hardware: list[str] = Field(default_factory=list)
    accessories: list[str] = Field(default_factory=list)
    words: list[str] = Field(default_factory=list)


class PriceEstimateRequest(BaseModel):
    brand: str
    category: str | None = None
    shape: str | None = None
    rank: str | None = None
    title: str
    sold_after: date | None = None
    limit: int = Field(default=20, ge=1, le=100)


class PriceRange(BaseModel):
    low: int
    mid: int
    high: int


class ComparableSale(BaseModel):
    item_id: str
    sold_date: date | None = None
    brand: str
    title: str
    rank: str | None = None
    category: str | None = None
    shape: str | None = None
    price_jpy: int
    item_url: str | None = None
    image_url: str | None = None
    score: float
    score_reasons: list[str]
    extracted_tokens: ExtractedTokens


class PriceEstimateResponse(BaseModel):
    market_price_jpy: PriceRange | None
    purchase_offer_jpy: PriceRange | None
    confidence: float
    missing_inputs: list[str]
    extracted_tokens: ExtractedTokens
    comparable_count: int
    comparables: list[ComparableSale]
