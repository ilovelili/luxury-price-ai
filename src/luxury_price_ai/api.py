from __future__ import annotations

import base64
from html import escape
import hmac
import mimetypes
from typing import Any

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx

from luxury_price_ai.analysis import analyze_auction_sales
from luxury_price_ai.config import get_settings
from luxury_price_ai.estimator import estimate_price
from luxury_price_ai.intake import (
    build_auction_request_from_image_inspection,
    build_price_request_from_form,
    image_analysis_confidence,
    image_analysis_missing_inputs,
)
from luxury_price_ai.models import (
    AuctionAnalysisRequest,
    AuctionAnalysisResponse,
    DifyFileReference,
    DifyImageInspectionRequest,
    ImageAuctionAnalysisResponse,
    ImageInspectionResponse,
    PriceEstimateRequest,
    PriceEstimateResponse,
)
from luxury_price_ai.storage import DatabaseConfigError, PostgresStore
from luxury_price_ai.vision import (
    RECOMMENDED_PHOTO_ANGLES,
    ImagePayload,
    VisionConfigError,
    VisionInputError,
    inspect_luxury_image_payloads,
    inspect_luxury_images,
)

app = FastAPI(title="Auction Sales Analysis", version="0.1.0")

CATEGORY_OPTIONS = [
    "ブランドバッグ",
    "財布",
    "時計",
    "アクセサリー",
    "服",
    "スニーカー・靴",
    "貴金属",
    "美術品・骨董品",
]

BRAND_OPTIONS = [
    "CHANEL",
    "LOUIS VUITTON",
    "HERMES",
    "GUCCI",
    "PRADA",
    "DIOR",
    "CELINE",
    "FENDI",
    "ROLEX",
    "CARTIER",
    "その他・不明",
]

SHAPE_OPTIONS = [
    "ショルダーバッグ",
    "ハンドバッグ",
    "トートバッグ",
    "チェーンウォレット",
    "財布",
    "時計",
    "アクセサリー",
    "服",
    "スニーカー・靴",
    "その他",
]

CONDITION_OPTIONS = [
    "新品・未使用",
    "ほぼ新品",
    "使用感少ない",
    "使用感あり",
    "古い・ダメージあり",
    "不明",
]

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse(url="/image-auction-analysis", status_code=302)


@app.get("/appraisal", include_in_schema=False)
def legacy_appraisal() -> RedirectResponse:
    return RedirectResponse(url="/image-auction-analysis", status_code=302)


@app.get("/auction-analysis", include_in_schema=False)
def auction_analysis_page() -> RedirectResponse:
    return RedirectResponse(url="/image-auction-analysis", status_code=302)


@app.post("/auction-analysis/search", include_in_schema=False)
def submit_auction_analysis_form(
    item_category: str = Form(...),
    brand: str = Form(...),
    item_shape: str = Form(...),
    item_name: str = Form(...),
    condition_status: str = Form(...),
    item_color: str = Form(default=""),
    item_description: str = Form(default=""),
    item_images: list[UploadFile] = File(default=[]),
) -> RedirectResponse:
    return RedirectResponse(url="/image-auction-analysis", status_code=303)


@app.get("/image-auction-analysis", response_class=HTMLResponse, include_in_schema=False)
def image_auction_analysis_page() -> HTMLResponse:
    return HTMLResponse(render_image_auction_analysis_page())


@app.post("/image-auction-analysis/search", response_class=HTMLResponse, include_in_schema=False)
def submit_image_auction_analysis_form(
    item_category: str = Form(default=""),
    brand: str = Form(default=""),
    item_shape: str = Form(default=""),
    item_name: str = Form(default=""),
    condition_status: str = Form(default=""),
    item_color: str = Form(default=""),
    item_description: str = Form(default=""),
    item_images: list[UploadFile] = File(default=[]),
) -> HTMLResponse:
    form_values = {
        "item_category": item_category,
        "brand": brand,
        "item_shape": item_shape,
        "item_name": item_name,
        "item_color": item_color,
        "condition_status": condition_status,
        "item_description": item_description,
    }
    image_names = [
        image.filename
        for image in item_images
        if image.filename
    ]
    try:
        response = run_image_auction_analysis(
            item_images,
            brand=brand,
            item_category=item_category,
            item_shape=item_shape,
            item_name=item_name,
            item_color=item_color,
            condition_status=condition_status,
            item_description=item_description,
        )
    except HTTPException as exc:
        return HTMLResponse(
            render_image_auction_analysis_page(
                form_values=form_values,
                image_names=image_names,
                error=str(exc.detail),
            ),
            status_code=exc.status_code,
        )

    return HTMLResponse(
        render_image_auction_analysis_page(
            form_values=form_values,
            image_names=image_names,
            response=response,
        )
    )


@app.post("/image-inspection/analyze", response_model=ImageInspectionResponse)
def image_inspection_analyze(
    item_images: list[UploadFile] = File(default=[]),
    x_api_key: str | None = Header(default=None),
) -> ImageInspectionResponse:
    settings = get_settings()
    require_api_key(settings.app_api_key, x_api_key)
    return run_image_inspection(item_images)


@app.post("/image-inspection/analyze-dify", response_model=ImageInspectionResponse)
def image_inspection_analyze_dify(
    request: DifyImageInspectionRequest,
    x_api_key: str | None = Header(default=None),
) -> ImageInspectionResponse:
    settings = get_settings()
    require_api_key(settings.app_api_key, x_api_key)
    payloads = resolve_dify_image_payloads(request, settings.dify_api_key)
    return run_image_inspection_payloads(payloads)


@app.post("/price-estimate", response_model=PriceEstimateResponse)
def price_estimate(
    request: PriceEstimateRequest,
    x_api_key: str | None = Header(default=None),
) -> PriceEstimateResponse:
    settings = get_settings()
    require_api_key(settings.app_api_key, x_api_key)
    return run_estimate(request)


@app.post("/auction-analysis", response_model=AuctionAnalysisResponse)
def auction_analysis(
    request: AuctionAnalysisRequest,
    x_api_key: str | None = Header(default=None),
) -> AuctionAnalysisResponse:
    settings = get_settings()
    require_api_key(settings.app_api_key, x_api_key)
    return run_auction_analysis(request)


@app.post("/image-auction-analysis", response_model=ImageAuctionAnalysisResponse)
def image_auction_analysis(
    item_category: str = Form(default=""),
    brand: str = Form(default=""),
    item_shape: str = Form(default=""),
    item_name: str = Form(default=""),
    condition_status: str = Form(default=""),
    item_color: str = Form(default=""),
    item_description: str = Form(default=""),
    item_images: list[UploadFile] = File(default=[]),
    x_api_key: str | None = Header(default=None),
) -> ImageAuctionAnalysisResponse:
    settings = get_settings()
    require_api_key(settings.app_api_key, x_api_key)
    return run_image_auction_analysis(
        item_images,
        brand=brand,
        item_category=item_category,
        item_shape=item_shape,
        item_name=item_name,
        item_color=item_color,
        condition_status=condition_status,
        item_description=item_description,
    )


def run_estimate(request: PriceEstimateRequest) -> PriceEstimateResponse:
    settings = get_settings()
    candidates = fetch_candidate_sales(request.brand, request.category, request.sold_after)
    return estimate_price(request, candidates, settings)


def fetch_candidate_sales(
    brand: str,
    category: str | None,
    sold_after,
):
    settings = get_settings()
    try:
        store = PostgresStore(settings.database_url or "")
        return store.fetch_candidates(
            brand=brand,
            category=category,
            sold_after=sold_after,
        )
    except DatabaseConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"database query failed: {exc}") from exc


def run_auction_analysis(request: AuctionAnalysisRequest) -> AuctionAnalysisResponse:
    candidates = fetch_candidate_sales(request.brand, request.category, request.sold_after)
    return analyze_auction_sales(request, candidates)


def run_strict_auction_analysis(
    request: AuctionAnalysisRequest,
    estimate: PriceEstimateResponse,
    candidates,
) -> AuctionAnalysisResponse:
    qualified_ids = {
        comparable.item_id
        for comparable in estimate.comparables
        if comparable.match_quality in {"exact", "close"}
    }
    if not qualified_ids:
        return analyze_auction_sales(request, [])

    return analyze_auction_sales(
        request,
        [candidate for candidate in candidates if candidate.item_id in qualified_ids],
    )


def run_image_inspection(images: list[UploadFile]) -> ImageInspectionResponse:
    try:
        return inspect_luxury_images(images, get_settings())
    except VisionInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VisionConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"image inspection failed: {exc}") from exc


def run_image_auction_analysis(
    images: list[UploadFile],
    *,
    brand: str = "",
    item_category: str = "",
    item_shape: str = "",
    item_name: str = "",
    item_color: str = "",
    condition_status: str = "",
    item_description: str = "",
) -> ImageAuctionAnalysisResponse:
    if not has_uploaded_images(images):
        base_request = build_price_request_from_form(
            brand=brand,
            item_category=item_category,
            item_shape=item_shape,
            item_name=item_name,
            item_color=item_color,
            condition_status=condition_status,
            item_description=item_description,
            limit=50,
        )
        request = AuctionAnalysisRequest.model_validate(base_request.model_dump())
        estimate_request = PriceEstimateRequest.model_validate(
            {
                **request.model_dump(),
                "limit": 20,
            }
        )
        candidates = fetch_candidate_sales(request.brand, request.category, request.sold_after)
        estimate = estimate_price(estimate_request, candidates, get_settings())
        analysis = run_strict_auction_analysis(request, estimate, candidates)
        return ImageAuctionAnalysisResponse(
            inspection=None,
            inferred_request=request,
            analysis=analysis,
            estimate=estimate,
            confidence=estimate.confidence,
            missing_inputs=estimate.missing_inputs,
        )

    inspection = run_image_inspection(images)
    request = build_auction_request_from_image_inspection(
        inspection,
        brand=brand,
        item_category=item_category,
        item_shape=item_shape,
        item_name=item_name,
        item_color=item_color,
        condition_status=condition_status,
        item_description=item_description,
    )
    estimate_request = PriceEstimateRequest.model_validate(
        {
            **request.model_dump(),
            "limit": 20,
        }
    )
    candidates = fetch_candidate_sales(request.brand, request.category, request.sold_after)
    estimate = estimate_price(estimate_request, candidates, get_settings())
    analysis = run_strict_auction_analysis(request, estimate, candidates)
    missing_inputs = image_analysis_missing_inputs(inspection, request)
    return ImageAuctionAnalysisResponse(
        inspection=inspection,
        inferred_request=request,
        analysis=analysis,
        estimate=estimate,
        confidence=image_analysis_confidence(
            inspection,
            request,
            analysis.record_count,
            missing_inputs,
        ),
        missing_inputs=missing_inputs,
    )


def has_uploaded_images(images: list[UploadFile]) -> bool:
    return any(image.filename or image.content_type for image in images)


def run_image_inspection_payloads(images: list[ImagePayload]) -> ImageInspectionResponse:
    try:
        return inspect_luxury_image_payloads(images, get_settings())
    except VisionInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VisionConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"image inspection failed: {exc}") from exc


def resolve_dify_image_payloads(
    request: DifyImageInspectionRequest,
    dify_api_key: str | None,
) -> list[ImagePayload]:
    references = [
        *request.item_images,
        *request.item_photos,
        *request.files,
    ]
    payloads = []
    for reference in references:
        payload = image_payload_from_dify_reference(reference, dify_api_key)
        if payload is not None:
            payloads.append(payload)
    if not payloads:
        raise HTTPException(status_code=400, detail="Difyから画像ファイルを取得できませんでした")
    return payloads


def image_payload_from_dify_reference(
    reference: DifyFileReference,
    dify_api_key: str | None,
) -> ImagePayload | None:
    data = reference.model_dump()
    url = first_string(
        data,
        "url",
        "remote_url",
        "download_url",
        "signed_url",
        "preview_url",
    )
    filename = first_string(data, "filename", "name") or "dify-image"
    content_type = first_string(data, "mime_type", "content_type") or guess_image_content_type(filename)

    if url and url.startswith("data:"):
        return image_payload_from_data_url(url, filename, content_type)
    if url and url.startswith(("http://", "https://")):
        return download_image_payload(url, filename, content_type, dify_api_key)
    return None


def image_payload_from_data_url(
    url: str,
    filename: str,
    fallback_content_type: str,
) -> ImagePayload:
    header, _, encoded = url.partition(",")
    if not encoded:
        raise HTTPException(status_code=400, detail="Dify画像data URLが不正です")
    content_type = fallback_content_type
    if header.startswith("data:") and ";" in header:
        content_type = header.removeprefix("data:").split(";", 1)[0]
    return ImagePayload(
        filename=filename,
        content_type=content_type,
        content=base64.b64decode(encoded),
    )


def download_image_payload(
    url: str,
    filename: str,
    fallback_content_type: str,
    dify_api_key: str | None,
) -> ImagePayload:
    headers = {}
    if dify_api_key and "dify" in url:
        headers["Authorization"] = f"Bearer {dify_api_key}"
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Dify画像を取得できませんでした: HTTP {response.status_code}")
    content_type = response.headers.get("content-type", "").split(";", 1)[0] or fallback_content_type
    return ImagePayload(
        filename=filename,
        content_type=content_type,
        content=response.content,
    )


def first_string(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def guess_image_content_type(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "image/jpeg"


def require_api_key(expected: str | None, provided: str | None) -> None:
    if not expected:
        return
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def render_image_auction_analysis_page(
    form_values: dict[str, str] | None = None,
    image_names: list[str] | None = None,
    response: ImageAuctionAnalysisResponse | None = None,
    error: str | None = None,
) -> str:
    image_names = image_names or []
    form_values = form_values or {}
    result = render_image_auction_analysis_result(image_names, response, error)
    return render_page_shell(
        form_values=form_values,
        result=result,
        page_title="Auction Sales Analysis",
        heading="Auction Sales Analysis",
        lede="商品写真または入力条件からEcoAuc/Ecoringの相場表、価格レンジ、落札例を確認します。",
        form_action="/image-auction-analysis/search",
        submit_label="相場表を見る",
        show_image_upload=False,
        form_body=render_image_auction_analysis_form_body(form_values),
    )


def render_page_shell(
    *,
    form_values: dict[str, str],
    result: str,
    page_title: str,
    heading: str,
    lede: str,
    form_action: str,
    submit_label: str,
    show_image_upload: bool,
    form_body: str | None = None,
) -> str:
    image_upload = render_image_upload_control() if show_image_upload else ""
    controls = form_body if form_body is not None else render_appraisal_form_body(
        form_values=form_values,
        image_upload=image_upload,
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(page_title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #080807;
      --panel: #12110f;
      --panel-2: #181613;
      --ink: #f3eee5;
      --muted: #a99d8a;
      --line: #302a22;
      --accent: #a88654;
      --accent-ink: #10100e;
      --warn: #d0a15d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    header {{
      width: min(1160px, calc(100vw - 32px));
      margin: 28px auto 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
    }}
    main {{
      width: min(1160px, calc(100vw - 32px));
      margin: 18px auto 28px;
      display: grid;
      grid-template-columns: minmax(360px, 560px) 1fr;
      gap: 24px;
      align-items: start;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 26px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    p {{ margin: 0 0 14px; }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
    }}
    .brandmark {{
      color: var(--accent);
      letter-spacing: 6px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 22px;
    }}
    nav {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    nav a {{
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--ink);
      text-decoration: none;
      padding: 8px 10px;
      background: var(--panel);
      font-size: 14px;
    }}
    nav a.active {{
      background: var(--accent);
      border-color: var(--accent);
      color: var(--accent-ink);
      font-weight: 700;
    }}
    .lede {{ color: var(--muted); }}
    label {{
      display: block;
      margin: 16px 0 6px;
      font-weight: 650;
    }}
    textarea, select, input[type="text"], input[type="file"] {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel-2);
      color: var(--ink);
      font: inherit;
    }}
    select, input[type="text"] {{
      height: 44px;
      padding: 0 12px;
    }}
    textarea {{
      min-height: 96px;
      padding: 12px;
      resize: vertical;
    }}
    input[type="file"] {{
      padding: 10px;
    }}
    button {{
      margin-top: 18px;
      width: 100%;
      border: 0;
      border-radius: 6px;
      background: #6f5b39;
      color: #0f0e0c;
      padding: 12px 14px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      opacity: 0.78;
      transition: background 160ms ease, opacity 160ms ease, transform 160ms ease;
    }}
    form:valid button {{
      background: #d8b775;
      color: #070706;
      opacity: 1;
    }}
    form:valid button:hover {{
      background: #e4c889;
      transform: translateY(-1px);
    }}
    .hint, .small {{
      color: var(--muted);
      font-size: 13px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 12px 0 18px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: var(--panel-2);
    }}
    .metric b {{
      display: block;
      font-size: 20px;
    }}
    .tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 8px 0 16px;
    }}
    .tag {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 9px;
      background: var(--panel-2);
      font-size: 13px;
    }}
    .warning {{
      color: var(--warn);
      background: #201811;
      border: 1px solid #5a4124;
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 14px;
    }}
    .photo-guide {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel-2);
      color: var(--muted);
      margin-top: 10px;
      padding: 12px;
      font-size: 13px;
    }}
    .photo-guide strong {{
      color: var(--ink);
      display: block;
      margin-bottom: 6px;
    }}
    .photo-guide ul {{
      margin: 0;
      padding-left: 18px;
    }}
    .comparable {{
      border-top: 1px solid var(--line);
      padding: 12px 0;
    }}
    .comparable:first-of-type {{ border-top: 0; }}
    .comparable a {{ color: var(--accent); }}
    .chart {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
      padding: 14px;
      margin: 12px 0 18px;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(90px, 150px) 1fr 44px;
      gap: 10px;
      align-items: center;
      margin: 8px 0;
      font-size: 13px;
    }}
    .bar-track {{
      height: 12px;
      background: #242019;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      background: var(--accent);
      min-width: 2px;
    }}
    .line-chart {{
      width: 100%;
      height: 190px;
      margin-top: 8px;
      overflow: visible;
    }}
    .line-chart path {{
      fill: none;
      stroke: #8ca68c;
      stroke-width: 3;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    .line-chart .axis {{
      stroke: var(--line);
      stroke-width: 1;
    }}
    .line-chart .grid-line {{
      stroke: var(--line);
      stroke-width: 1;
      opacity: 0.7;
    }}
    .line-chart text {{
      fill: var(--muted);
      font-size: 13px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .line-chart circle {{
      fill: var(--accent);
      stroke: var(--panel-2);
      stroke-width: 2;
    }}
    .chart-labels {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      margin-top: 8px;
    }}
    @media (max-width: 860px) {{
      header {{ align-items: flex-start; flex-direction: column; }}
      nav {{ justify-content: flex-start; }}
      main {{ grid-template-columns: 1fr; }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="brandmark">TRUNK</div>
  </header>
  <main>
    <section class="panel">
      <h1>{escape(heading)}</h1>
      <p class="lede">{escape(lede)}</p>
      <form action="{escape(form_action)}" method="post" enctype="multipart/form-data">
        {controls}
        <button type="submit">{escape(submit_label)}</button>
      </form>
    </section>
    <section class="panel">
      {result}
    </section>
  </main>
</body>
	</html>"""


def render_appraisal_form_body(form_values: dict[str, str], image_upload: str) -> str:
    return f"""<label for="item_category">カテゴリ</label>
{render_select("item_category", CATEGORY_OPTIONS, form_values.get("item_category", "ブランドバッグ"))}

<label for="brand">ブランド</label>
{render_select("brand", BRAND_OPTIONS, form_values.get("brand", "CHANEL"))}

<label for="item_shape">アイテム種別・形状</label>
{render_select("item_shape", SHAPE_OPTIONS, form_values.get("item_shape", "ショルダーバッグ"))}

<label for="item_name">アイテム名・型番</label>
<input id="item_name" name="item_name" type="text" required placeholder="例: マトラッセ キャビアスキン" value="{escape(form_values.get("item_name", ""))}">

<label for="item_color">カラー</label>
<input id="item_color" name="item_color" type="text" placeholder="例: 黒 / ゴールド金具" value="{escape(form_values.get("item_color", ""))}">

<label for="condition_status">状態</label>
{render_select("condition_status", CONDITION_OPTIONS, form_values.get("condition_status", "使用感少ない"))}

<label for="item_description">商品説明・補足</label>
<textarea id="item_description" name="item_description" placeholder="サイズ感、購入時期、付属品、ダメージなど">{escape(form_values.get("item_description", ""))}</textarea>

{image_upload}"""


def render_image_auction_analysis_form_body(form_values: dict[str, str]) -> str:
    angle_items = "".join(f"<li>{escape(angle)}</li>" for angle in RECOMMENDED_PHOTO_ANGLES)
    return f"""<label for="item_images">商品写真 任意</label>
<input id="item_images" name="item_images" type="file" accept="image/*" multiple>
<p class="hint">写真がある場合はブランド・型・状態候補を読み取り、写真なしの場合は下の入力条件で相場表を検索します。</p>
<div class="photo-guide">
  <strong>推奨アングル</strong>
  <ul>{angle_items}</ul>
</div>

<label for="item_category">カテゴリ 任意</label>
{render_optional_select("item_category", CATEGORY_OPTIONS, form_values.get("item_category", ""))}

<label for="brand">ブランド 任意</label>
{render_optional_select("brand", BRAND_OPTIONS, form_values.get("brand", ""))}

<label for="item_shape">アイテム種別・形状 任意</label>
{render_optional_select("item_shape", SHAPE_OPTIONS, form_values.get("item_shape", ""))}

<label for="item_name">アイテム名・型番 任意</label>
<input id="item_name" name="item_name" type="text" placeholder="例: マトラッセ キャビアスキン" value="{escape(form_values.get("item_name", ""))}">

<label for="item_color">カラー 任意</label>
<input id="item_color" name="item_color" type="text" placeholder="例: 黒 / ゴールド金具" value="{escape(form_values.get("item_color", ""))}">

<label for="condition_status">状態 任意</label>
{render_optional_select("condition_status", CONDITION_OPTIONS, form_values.get("condition_status", ""))}

<label for="item_description">商品説明・補足 任意</label>
<textarea id="item_description" name="item_description" placeholder="サイズ感、購入時期、付属品、ダメージなど">{escape(form_values.get("item_description", ""))}</textarea>"""


def render_select(name: str, options: list[str], selected: str) -> str:
    option_html = "\n".join(
        f'<option value="{escape(option)}"{selected_attr(option, selected)}>{escape(option)}</option>'
        for option in options
    )
    return f'<select id="{escape(name)}" name="{escape(name)}" required>{option_html}</select>'


def render_optional_select(name: str, options: list[str], selected: str) -> str:
    option_html = '<option value="">画像から推定</option>\n' + "\n".join(
        f'<option value="{escape(option)}"{selected_attr(option, selected)}>{escape(option)}</option>'
        for option in options
    )
    return f'<select id="{escape(name)}" name="{escape(name)}">{option_html}</select>'


def render_image_upload_control() -> str:
    return """<label for="item_images">商品写真</label>
<input id="item_images" name="item_images" type="file" accept="image/*" multiple required>
<p class="hint">正面、背面、角、内側/シリアル、金具、ダメージ箇所</p>"""


def selected_attr(option: str, selected: str) -> str:
    return " selected" if option == selected else ""


def render_analysis_result(
    image_names: list[str],
    normalized_request: AuctionAnalysisRequest | None,
    analysis: AuctionAnalysisResponse | None,
    error: str | None,
) -> str:
    if error:
        return f"<h2>Analysis failed</h2><div class=\"warning\">{escape(error)}</div>"
    if not analysis or not normalized_request:
        return """<h2>How this works</h2>
<p>EcoAuc/Ecoring CSV data in Supabase is searched by explicit filters. The app returns matching auction records, median, average, quartiles, and recent movement.</p>
<p class="small">Images are kept as review context only. They are not used to calculate prices.</p>"""

    normalized = render_normalized_request(normalized_request)
    stats = render_stats(analysis)
    trend = render_trend(analysis)
    charts = render_analysis_charts(analysis)
    records = "\n".join(render_auction_record(item) for item in analysis.records[:10])
    return f"""
<h2>Analysis result</h2>
{normalized}
{stats}
{trend}
{charts}
<h2>Auction records</h2>
{records or '<p>No matching auction records found.</p>'}
"""


def render_image_auction_analysis_result(
    image_names: list[str],
    response: ImageAuctionAnalysisResponse | None,
    error: str | None,
) -> str:
    if error:
        return f"<h2>Image auction analysis failed</h2><div class=\"warning\">{escape(error)}</div>"
    if not response:
        return """<h2>How this works</h2>
<p>商品写真または入力条件を検索条件に変換し、相場表DBから近い落札記録、相場統計、価格レンジを表示します。</p>
<p class="small">画像だけで真贋や最終査定額は断定しません。写真なしでもブランドや形状などの入力条件だけで分析できます。</p>"""

    inspection = response.inspection
    analysis = response.analysis
    estimate = response.estimate
    normalized = render_normalized_request(response.inferred_request)
    image_summary = render_image_analysis_summary(image_names, response)
    market = render_price_range("推定市場価格", estimate.market_price_jpy)
    offer = render_price_range("買取提示レンジ", estimate.purchase_offer_jpy)
    stats = render_stats(analysis)
    trend = render_trend(analysis)
    charts = render_analysis_charts(analysis)
    records = "\n".join(render_auction_record(item) for item in analysis.records[:10])
    missing = render_text_list(response.missing_inputs, "追加で必要な情報はありません。")
    quality = render_comparable_quality_summary(estimate)
    return f"""
<h2>Auction sales analysis result</h2>
{image_summary}
{normalized}
<div class="grid">
  {market}
  {offer}
  <div class="metric"><span>Confidence</span><b>{response.confidence:.0%}</b><small>商品特定 + 厳格比較</small></div>
  {render_condition_metric(inspection)}
  <div class="metric"><span>条件一致</span><b>{analysis.record_count:,}件</b><small>表示 {len(analysis.records):,}件</small></div>
</div>
{quality}
{render_image_candidates_section(inspection)}
<h2>Missing inputs</h2>
{missing}
<h2>Market table</h2>
{stats}
{trend}
{charts}
<h2>Auction records</h2>
{records or '<p>No matching auction records found.</p>'}
"""


def render_image_candidates_section(inspection: ImageInspectionResponse | None) -> str:
    if not inspection:
        return ""
    brand_candidates = render_compact_brand_candidates(inspection)
    model_candidates = render_compact_model_candidates(inspection)
    return f"""<h2>Image-derived candidates</h2>
{brand_candidates}
{model_candidates}
"""


def render_image_analysis_summary(
    image_names: list[str],
    response: ImageAuctionAnalysisResponse,
) -> str:
    if not response.inspection:
        return """<div class="warning">写真なしで分析しました。写真を追加するとブランド・型・状態候補を自動補完できます。</div>"""
    names = ", ".join(escape(name) for name in image_names[:6]) or "uploaded images"
    extra = "" if len(image_names) <= 6 else f" and {len(image_names) - 6} more"
    warnings = " / ".join(response.inspection.warnings[:2])
    return f"""<div class="warning">画像 {len(image_names)} 件を解析しました: {names}{extra}。{escape(warnings)}</div>"""


def render_condition_metric(inspection: ImageInspectionResponse | None) -> str:
    if not inspection:
        return """<div class="metric"><span>画像上の状態</span><b>-</b><small>写真なし</small></div>"""
    return f"""<div class="metric"><span>画像上の状態</span><b>{escape(inspection.condition_status)}</b><small>画像Confidence {inspection.condition_confidence:.0%}</small></div>"""


def render_compact_brand_candidates(inspection: ImageInspectionResponse) -> str:
    tags = "".join(
        f"<span class=\"tag\">{escape(candidate.brand)} {candidate.confidence:.0%}</span>"
        for candidate in inspection.brand_candidates[:5]
    )
    return f"<div class=\"tags\">{tags}</div>" if tags else "<p>ブランド候補はありません。</p>"


def render_compact_model_candidates(inspection: ImageInspectionResponse) -> str:
    if not inspection.model_candidates:
        return "<p>モデル候補は写真から十分に確認できませんでした。</p>"
    rows = "\n".join(
        f"""<div class="comparable">
  <strong>{escape(candidate.brand)} {escape(candidate.model)}</strong> <span class="small">{candidate.confidence:.0%}</span>
  <div class="small">{escape(candidate.evidence)}</div>
</div>"""
        for candidate in inspection.model_candidates[:3]
    )
    return rows


def render_text_list(values: list[str], empty_text: str) -> str:
    if not values:
        return f"<p>{escape(empty_text)}</p>"
    items = "".join(f"<li>{escape(value)}</li>" for value in values)
    return f"<ul>{items}</ul>"


def render_normalized_request(request: AuctionAnalysisRequest | PriceEstimateRequest) -> str:
    values = [
        ("brand", request.brand),
        ("category", request.category),
        ("shape", request.shape),
        ("rank", request.rank),
    ]
    tags = "".join(
        f"<span class=\"tag\">{escape(label)}: {escape(value or 'unknown')}</span>"
        for label, value in values
    )
    return f"<div class=\"tags\">{tags}</div>"


def render_price_range(label: str, price_range) -> str:
    if not price_range:
        return f"<div class=\"metric\"><span>{escape(label)}</span><b>算出不可</b><small>厳格な比較対象が不足</small></div>"
    return f"""<div class="metric">
  <span>{escape(label)}</span>
  <b>{price_range.mid:,}円</b>
  <small>{price_range.low:,}円 - {price_range.high:,}円</small>
    </div>"""


def render_comparable_quality_summary(estimate: PriceEstimateResponse) -> str:
    counts = {
        "exact": 0,
        "close": 0,
        "weak": 0,
        "excluded": 0,
    }
    for comparable in estimate.comparables:
        if comparable.match_quality in counts:
            counts[comparable.match_quality] += 1
    if estimate.market_price_jpy:
        lead = "価格レンジは exact / close comparable のみで算出しています。"
    else:
        lead = "型・素材・色・金具・状態が十分に揃った comparable が不足しているため、価格レンジは出していません。"
    review_examples = [
        comparable
        for comparable in estimate.comparables
        if comparable.match_quality in {"weak", "excluded"}
    ][:3]
    weak_html = "".join(
        f"""<div class="comparable">
  <strong>{escape(item.match_quality)}</strong> <span class="small">{escape(item.title)}</span>
  <div class="small">{escape(', '.join(item.exclusion_reasons or item.score_reasons[:3]))}</div>
</div>"""
        for item in review_examples
    )
    return f"""<div class="warning">{escape(lead)}</div>
<div class="tags">
  <span class="tag">exact: {counts["exact"]}</span>
  <span class="tag">close: {counts["close"]}</span>
  <span class="tag">weak: {counts["weak"]}</span>
  <span class="tag">excluded: {counts["excluded"]}</span>
  <span class="tag">qualified: {estimate.qualified_comparable_count}</span>
</div>
{weak_html}"""


def render_stats(analysis: AuctionAnalysisResponse) -> str:
    stats = analysis.stats
    return f"""<div class="grid">
  <div class="metric"><span>中央値</span><b>{format_jpy(stats.median_jpy)}</b><small>p25 {format_jpy(stats.p25_jpy)} / p75 {format_jpy(stats.p75_jpy)}</small></div>
  <div class="metric"><span>平均値</span><b>{format_jpy(stats.average_jpy)}</b><small>min {format_jpy(stats.min_jpy)} / max {format_jpy(stats.max_jpy)}</small></div>
  <div class="metric"><span>落札件数</span><b>{stats.count:,}件</b><small>表示 {len(analysis.records):,}件 / 条件一致 {analysis.record_count:,}件</small></div>
</div>"""


def render_trend(analysis: AuctionAnalysisResponse) -> str:
    trend = analysis.trend
    change = "-"
    if trend.change_jpy is not None and trend.change_percent is not None:
        sign = "+" if trend.change_jpy > 0 else ""
        change = f"{sign}{trend.change_jpy:,}円 / {sign}{trend.change_percent:.1f}%"
    return f"""<div class="grid">
  <div class="metric"><span>直近{trend.recent_period_days}日 中央値</span><b>{format_jpy(trend.recent_median_jpy)}</b><small>{trend.recent_count:,}件</small></div>
  <div class="metric"><span>前{trend.recent_period_days}日 中央値</span><b>{format_jpy(trend.previous_median_jpy)}</b><small>{trend.previous_count:,}件</small></div>
  <div class="metric"><span>値動き</span><b>{escape(change)}</b><small>{escape(trend.direction)}</small></div>
</div>"""


def render_analysis_charts(analysis: AuctionAnalysisResponse) -> str:
    return f"""
<h2>Charts</h2>
{render_histogram(analysis)}
{render_daily_trend_chart(analysis)}
"""


def render_histogram(analysis: AuctionAnalysisResponse) -> str:
    if not analysis.histogram:
        return """<div class="chart"><strong>価格分布</strong><p class="small">No price data.</p></div>"""
    max_count = max((item.count for item in analysis.histogram), default=1)
    rows = "\n".join(
        f"""<div class="bar-row">
  <span>{escape(item.label)}円</span>
  <div class="bar-track"><div class="bar-fill" style="width:{bar_width(item.count, max_count)}%"></div></div>
  <span>{item.count:,}</span>
</div>"""
        for item in analysis.histogram
    )
    return f"""<div class="chart">
  <strong>価格分布</strong>
  {rows}
</div>"""


def render_daily_trend_chart(analysis: AuctionAnalysisResponse) -> str:
    if not analysis.window_trend:
        return """<div class="chart"><strong>7日間中央値</strong><p class="small">No dated records.</p></div>"""
    latest = analysis.window_trend[-1]
    return f"""<div class="chart">
  <strong>7日間中央値</strong>
  <p class="small">直近3か月を7日ごとに集計 / Latest {escape(latest.label)}: {latest.median_jpy:,}円 / {latest.count:,}件</p>
  {render_line_chart(analysis.window_trend)}
</div>"""


def render_line_chart(points) -> str:
    if len(points) == 1:
        point = points[0]
        return f"""<svg class="line-chart" viewBox="0 0 640 190" role="img" aria-label="7日間中央値">
  <line class="axis" x1="86" y1="10" x2="86" y2="170"></line>
  <text x="0" y="99">{format_axis_jpy(point.median_jpy)}</text>
  <circle cx="360" cy="95" r="5"><title>{escape(point.label)} {point.median_jpy:,}円</title></circle>
</svg>
<div class="chart-labels"><span>{escape(point.label)}</span></div>"""

    prices = [point.median_jpy for point in points]
    min_price = min(prices)
    max_price = max(prices)
    span = max(1, max_price - min_price)
    width = 640
    left_padding = 86
    right_padding = 8
    height = 170
    top_padding = 10
    chart_width = width - left_padding - right_padding
    x_step = chart_width / (len(points) - 1)
    coordinates = []
    for index, point in enumerate(points):
        x = round(left_padding + (index * x_step), 1)
        y = round(top_padding + ((max_price - point.median_jpy) / span * (height - top_padding)), 1)
        coordinates.append((x, y, point))

    path = " ".join(
        f"{'M' if index == 0 else 'L'} {x} {y}"
        for index, (x, y, _point) in enumerate(coordinates)
    )
    circles = "\n".join(
        f'  <circle cx="{x}" cy="{y}" r="4"><title>{escape(point.label)} {point.median_jpy:,}円 / {point.count:,}件</title></circle>'
        for x, y, point in coordinates
    )
    axis = render_y_axis(min_price, max_price, left_padding, right_padding, width, height, top_padding)
    labels = [
        points[0].label,
        points[len(points) // 2].label,
        points[-1].label,
    ]
    label_html = "".join(f"<span>{escape(label)}</span>" for label in labels)
    return f"""<svg class="line-chart" viewBox="0 0 640 190" role="img" aria-label="7日間中央値">
{axis}
  <path d="{escape(path)}"></path>
{circles}
  </svg>
<div class="chart-labels">{label_html}</div>"""


def render_y_axis(
    min_price: int,
    max_price: int,
    left_padding: int,
    right_padding: int,
    width: int,
    height: int,
    top_padding: int,
) -> str:
    values = [max_price, round((min_price + max_price) / 2), min_price]
    span = max(1, max_price - min_price)
    chart_right = width - right_padding
    rows = [f'  <line class="axis" x1="{left_padding}" y1="{top_padding}" x2="{left_padding}" y2="{height}"></line>']
    for value in values:
        y = round(top_padding + ((max_price - value) / span * (height - top_padding)), 1)
        rows.append(f'  <line class="grid-line" x1="{left_padding}" y1="{y}" x2="{chart_right}" y2="{y}"></line>')
        rows.append(f'  <text x="0" y="{y + 4}">{format_axis_jpy(value)}</text>')
    return "\n".join(rows)


def format_axis_jpy(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    return f"{round(value / 1000):,}k"


def bar_width(value: int, max_value: int) -> int:
    if max_value <= 0 or value <= 0:
        return 0
    return max(3, round((value / max_value) * 100))


def format_jpy(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,}円"


def render_auction_record(item) -> str:
    title = escape(item.title)
    url = item.item_url
    title_html = f"<a href=\"{escape(url)}\" target=\"_blank\" rel=\"noreferrer\">{title}</a>" if url else title
    image_html = ""
    if item.image_url:
        image_html = f' <a href="{escape(item.image_url)}" target="_blank" rel="noreferrer">画像</a>'
    sold_date = item.sold_date.isoformat() if item.sold_date else "unknown date"
    return f"""<div class="comparable">
  <strong>{item.price_jpy:,}円</strong> <span class="small">{escape(sold_date)} / rank {escape(item.rank or '-')} / {escape(item.shape or '-')}</span>
  <div>{title_html}{image_html}</div>
</div>"""
