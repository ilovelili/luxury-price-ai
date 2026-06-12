from __future__ import annotations

import hmac

from fastapi import FastAPI, Header, HTTPException

from luxury_price_ai.config import get_settings
from luxury_price_ai.estimator import estimate_price
from luxury_price_ai.models import PriceEstimateRequest, PriceEstimateResponse
from luxury_price_ai.storage import DatabaseConfigError, PostgresStore

app = FastAPI(title="Luxury Price AI", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/price-estimate", response_model=PriceEstimateResponse)
def price_estimate(
    request: PriceEstimateRequest,
    x_api_key: str | None = Header(default=None),
) -> PriceEstimateResponse:
    settings = get_settings()
    require_api_key(settings.app_api_key, x_api_key)
    try:
        store = PostgresStore(settings.database_url or "")
        candidates = store.fetch_candidates(
            brand=request.brand,
            category=request.category,
            sold_after=request.sold_after,
        )
    except DatabaseConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"database query failed: {exc}") from exc

    return estimate_price(request, candidates, settings)


def require_api_key(expected: str | None, provided: str | None) -> None:
    if not expected:
        return
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid or missing API key")
