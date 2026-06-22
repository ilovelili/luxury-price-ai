from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import httpx
from luxury_price_ai.config import Settings
from luxury_price_ai.models import ImageAuctionAnalysisResponse


@dataclass(frozen=True)
class DifyDraft:
    text: str
    raw_response: dict[str, Any]


class DifyConfigError(RuntimeError):
    pass


class DifyClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.dify_api_key:
            raise DifyConfigError("DIFY_API_KEY is not configured")
        self.base_url = settings.dify_base_url
        self.api_key = settings.dify_api_key
        self.user = settings.dify_user

    def run_appraisal_workflow(
        self,
        *,
        form_values: dict[str, str],
        analysis_response: ImageAuctionAnalysisResponse,
        images: list[object],
    ) -> DifyDraft:
        with httpx.Client(timeout=60) as client:
            files: list[dict[str, str]] = []
            payload = self._workflow_payload(
                form_values=form_values,
                analysis_response=analysis_response,
                files=files,
                rich_context=True,
            )
            response = client.post(f"{self.base_url}/workflows/run", headers=self._headers(), json=payload)
            if response.status_code == 400:
                fallback_payload = self._workflow_payload(
                    form_values=form_values,
                    analysis_response=analysis_response,
                    files=files,
                    rich_context=False,
                )
                response = client.post(
                    f"{self.base_url}/workflows/run",
                    headers=self._headers(),
                    json=fallback_payload,
                )
            response.raise_for_status()
            payload = response.json()
            return DifyDraft(text=extract_dify_text(payload), raw_response=payload)

    def _workflow_payload(
        self,
        *,
        form_values: dict[str, str],
        analysis_response: ImageAuctionAnalysisResponse,
        files: list[dict[str, str]],
        rich_context: bool,
    ) -> dict[str, Any]:
        inputs: dict[str, Any] = {
            "item_description": form_values.get("item_description", ""),
            "item_category": form_values.get("item_category", ""),
            "brand": form_values.get("brand", ""),
            "item_shape": form_values.get("item_shape", ""),
            "item_name": form_values.get("item_name", ""),
            "item_color": form_values.get("item_color", ""),
            "condition_status": form_values.get("condition_status", ""),
        }
        if files:
            inputs["item_photos"] = files
        if rich_context:
            inputs.update(build_appraisal_context_inputs(analysis_response))
        payload = {
            "inputs": inputs,
            "response_mode": "blocking",
            "user": self.user,
        }
        if files:
            payload["files"] = files
        return payload

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}


def build_appraisal_context_inputs(response: ImageAuctionAnalysisResponse) -> dict[str, str]:
    estimate = response.estimate
    analysis = response.analysis
    request = response.inferred_request
    records = [
        {
            "item_id": record.item_id,
            "title": record.title,
            "rank": record.rank,
            "shape": record.shape,
            "sold_date": record.sold_date.isoformat() if record.sold_date else None,
            "price_jpy": record.price_jpy,
            "item_url": record.item_url,
        }
        for record in analysis.records[:10]
    ]
    context = {
        "inferred_request": request.model_dump(mode="json"),
        "price_estimate": estimate.model_dump(mode="json"),
        "auction_stats": analysis.stats.model_dump(mode="json"),
        "auction_records": records,
        "image_inspection": response.inspection.model_dump(mode="json") if response.inspection else None,
        "confidence": response.confidence,
        "missing_inputs": response.missing_inputs,
    }
    market = estimate.market_price_jpy
    offer = estimate.purchase_offer_jpy
    return {
        "appraisal_context": json.dumps(context, ensure_ascii=False),
        "market_price_range": format_range(market),
        "purchase_offer_range": format_range(offer),
        "price_basis": estimate.price_basis,
        "confidence": f"{response.confidence:.0%}",
        "missing_inputs": "、".join(response.missing_inputs),
        "comparable_count": str(estimate.comparable_count),
        "qualified_comparable_count": str(estimate.qualified_comparable_count),
    }


def format_range(price_range) -> str:
    if not price_range:
        return "算出不可"
    return f"{price_range.low:,}円 - {price_range.mid:,}円 - {price_range.high:,}円"


def extract_dify_text(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    if isinstance(data, dict):
        outputs = data.get("outputs")
        if isinstance(outputs, dict):
            for key in ("text", "answer", "result", "output"):
                value = outputs.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            for value in outputs.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()
        value = data.get("answer")
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("answer", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
