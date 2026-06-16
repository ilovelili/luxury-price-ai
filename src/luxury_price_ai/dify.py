from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import UploadFile

from luxury_price_ai.config import Settings
from luxury_price_ai.models import PriceEstimateResponse


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
        estimate: PriceEstimateResponse,
        images: list[UploadFile],
    ) -> DifyDraft:
        with httpx.Client(timeout=60) as client:
            files = self._upload_images(client, images)
            response = client.post(
                f"{self.base_url}/workflows/run",
                headers=self._headers(),
                json={
                    "inputs": {
                        "item_description": form_values.get("item_description", ""),
                        "item_category": form_values.get("item_category", ""),
                        "brand": form_values.get("brand", ""),
                        "item_shape": form_values.get("item_shape", ""),
                        "item_name": form_values.get("item_name", ""),
                        "item_color": form_values.get("item_color", ""),
                        "condition_status": form_values.get("condition_status", ""),
                        "item_photos": files,
                    },
                    "files": files,
                    "response_mode": "blocking",
                    "user": self.user,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return DifyDraft(text=extract_dify_text(payload), raw_response=payload)

    def _upload_images(self, client: httpx.Client, images: list[UploadFile]) -> list[dict[str, str]]:
        uploaded: list[dict[str, str]] = []
        for image in images:
            if not image.filename or not image.content_type or not image.content_type.startswith("image/"):
                continue
            content = image.file.read()
            image.file.seek(0)
            if not content:
                continue
            response = client.post(
                f"{self.base_url}/files/upload",
                headers=self._headers(),
                data={"user": self.user},
                files={"file": (image.filename, content, image.content_type)},
            )
            response.raise_for_status()
            file_id = response.json().get("id")
            if file_id:
                uploaded.append(
                    {
                        "type": "image",
                        "transfer_method": "local_file",
                        "upload_file_id": file_id,
                    }
                )
        return uploaded

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}


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
