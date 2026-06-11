from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    margin_rate: float
    risk_discount_rate: float

    @property
    def offer_multiplier(self) -> float:
        return max(0.0, 1.0 - self.margin_rate - self.risk_discount_rate)


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL"),
        margin_rate=float(os.getenv("PRICE_MARGIN_RATE", "0.25")),
        risk_discount_rate=float(os.getenv("PRICE_RISK_DISCOUNT_RATE", "0.05")),
    )
