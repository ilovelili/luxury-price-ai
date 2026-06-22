from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    margin_rate: float
    risk_discount_rate: float
    app_api_key: str | None
    openai_api_key: str | None
    openai_vision_model: str
    gemini_api_key: str | None
    gemini_vision_model: str
    dify_api_key: str | None
    dify_base_url: str
    dify_user: str

    @property
    def offer_multiplier(self) -> float:
        return max(0.0, 1.0 - self.margin_rate - self.risk_discount_rate)


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL"),
        margin_rate=float(os.getenv("PRICE_MARGIN_RATE", "0.25")),
        risk_discount_rate=float(os.getenv("PRICE_RISK_DISCOUNT_RATE", "0.05")),
        app_api_key=os.getenv("APP_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_vision_model=os.getenv("OPENAI_VISION_MODEL", "gpt-5.5"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_vision_model=os.getenv("GEMINI_VISION_MODEL", "gemini-3.5-flash"),
        dify_api_key=os.getenv("DIFY_API_KEY"),
        dify_base_url=os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").rstrip("/"),
        dify_user=os.getenv("DIFY_USER", "luxury-price-appraisal-web"),
    )
