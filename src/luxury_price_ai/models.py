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


class AuctionAnalysisRequest(BaseModel):
    brand: str
    category: str | None = None
    shape: str | None = None
    rank: str | None = None
    title: str = ""
    sold_after: date | None = None
    limit: int = Field(default=50, ge=1, le=200)


class AuctionPriceStats(BaseModel):
    count: int
    average_jpy: int | None
    median_jpy: int | None
    p25_jpy: int | None
    p75_jpy: int | None
    min_jpy: int | None
    max_jpy: int | None


class AuctionTrend(BaseModel):
    recent_period_days: int
    recent_count: int
    previous_count: int
    recent_median_jpy: int | None
    previous_median_jpy: int | None
    change_jpy: int | None
    change_percent: float | None
    direction: str


class AuctionHistogramBin(BaseModel):
    label: str
    min_jpy: int
    max_jpy: int
    count: int


class AuctionMonthlyPoint(BaseModel):
    month: str
    count: int
    median_jpy: int
    average_jpy: int


class AuctionDailyPoint(BaseModel):
    date: date
    count: int
    median_jpy: int
    average_jpy: int


class AuctionWindowPoint(BaseModel):
    start_date: date
    end_date: date
    label: str
    count: int
    median_jpy: int
    average_jpy: int


class AuctionRecord(BaseModel):
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
    auction: str | None = None
    source_month: str | None = None


class AuctionAnalysisResponse(BaseModel):
    filters: dict[str, str | None]
    stats: AuctionPriceStats
    trend: AuctionTrend
    histogram: list[AuctionHistogramBin]
    monthly_trend: list[AuctionMonthlyPoint]
    daily_trend: list[AuctionDailyPoint]
    window_trend: list[AuctionWindowPoint]
    record_count: int
    records: list[AuctionRecord]


class ImageAuctionAnalysisResponse(BaseModel):
    inspection: "ImageInspectionResponse | None" = None
    inferred_request: AuctionAnalysisRequest
    analysis: AuctionAnalysisResponse
    estimate: PriceEstimateResponse
    confidence: float
    missing_inputs: list[str]


class BrandCandidate(BaseModel):
    brand: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str


class ModelCandidate(BaseModel):
    brand: str
    model: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    distinguishing_features: list[str] = Field(default_factory=list)


class ImageInspectionResponse(BaseModel):
    brand_candidates: list[BrandCandidate]
    model_candidates: list[ModelCandidate] = Field(default_factory=list)
    condition_status: str
    condition_confidence: float = Field(ge=0.0, le=1.0)
    visible_signals: list[str]
    missing_photo_angles: list[str]
    warnings: list[str]


class DifyFileReference(BaseModel):
    model_config = {"extra": "allow"}

    url: str | None = None
    remote_url: str | None = None
    download_url: str | None = None
    filename: str | None = None
    name: str | None = None
    mime_type: str | None = None
    content_type: str | None = None
    transfer_method: str | None = None
    upload_file_id: str | None = None


class DifyImageInspectionRequest(BaseModel):
    item_images: list[DifyFileReference] = Field(default_factory=list)
    item_photos: list[DifyFileReference] = Field(default_factory=list)
    files: list[DifyFileReference] = Field(default_factory=list)
