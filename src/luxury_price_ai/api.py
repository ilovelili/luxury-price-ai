from __future__ import annotations

from html import escape
import hmac

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from luxury_price_ai.config import get_settings
from luxury_price_ai.dify import DifyClient, DifyConfigError, DifyDraft
from luxury_price_ai.estimator import estimate_price
from luxury_price_ai.intake import build_price_request_from_form
from luxury_price_ai.models import PriceEstimateRequest, PriceEstimateResponse
from luxury_price_ai.storage import DatabaseConfigError, PostgresStore

app = FastAPI(title="Luxury Price AI", version="0.1.0")

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
    return RedirectResponse(url="/appraisal", status_code=302)


@app.get("/appraisal", response_class=HTMLResponse, include_in_schema=False)
def appraisal_form() -> HTMLResponse:
    return HTMLResponse(render_appraisal_page())


@app.post("/appraisal", response_class=HTMLResponse, include_in_schema=False)
def submit_appraisal_form(
    item_category: str = Form(...),
    brand: str = Form(...),
    item_shape: str = Form(...),
    item_name: str = Form(...),
    condition_status: str = Form(...),
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
    request = build_price_request_from_form(**form_values, limit=10)
    try:
        response = run_estimate(request)
    except HTTPException as exc:
        return HTMLResponse(
            render_appraisal_page(
                form_values=form_values,
                error=str(exc.detail),
            ),
            status_code=exc.status_code,
        )

    dify_draft, dify_error = run_dify_appraisal(form_values, response, item_images)
    image_names = [
        image.filename
        for image in item_images
        if image.filename
    ]
    return HTMLResponse(
        render_appraisal_page(
            form_values=form_values,
            image_names=image_names,
            normalized_request=request,
            estimate=response,
            dify_draft=dify_draft,
            dify_error=dify_error,
        )
    )


@app.post("/price-estimate", response_model=PriceEstimateResponse)
def price_estimate(
    request: PriceEstimateRequest,
    x_api_key: str | None = Header(default=None),
) -> PriceEstimateResponse:
    settings = get_settings()
    require_api_key(settings.app_api_key, x_api_key)
    return run_estimate(request)


def run_estimate(request: PriceEstimateRequest) -> PriceEstimateResponse:
    settings = get_settings()
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


def run_dify_appraisal(
    form_values: dict[str, str],
    estimate: PriceEstimateResponse,
    images: list[UploadFile],
) -> tuple[DifyDraft | None, str | None]:
    settings = get_settings()
    try:
        client = DifyClient(settings)
    except DifyConfigError:
        return None, None
    try:
        draft = client.run_appraisal_workflow(
            form_values=form_values,
            estimate=estimate,
            images=images,
        )
    except Exception as exc:
        return None, f"Appraisal workflow failed: {exc}"
    return draft, None


def require_api_key(expected: str | None, provided: str | None) -> None:
    if not expected:
        return
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def render_appraisal_page(
    form_values: dict[str, str] | None = None,
    image_names: list[str] | None = None,
    normalized_request: PriceEstimateRequest | None = None,
    estimate: PriceEstimateResponse | None = None,
    dify_draft: DifyDraft | None = None,
    dify_error: str | None = None,
    error: str | None = None,
) -> str:
    image_names = image_names or []
    form_values = form_values or {}
    result = render_result(image_names, normalized_request, estimate, dify_draft, dify_error, error)
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Luxury Price Appraisal</title>
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
    main {{
      width: min(1160px, calc(100vw - 32px));
      margin: 28px auto;
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
      text-align: center;
      margin: 34px 0 10px;
      color: var(--accent);
      letter-spacing: 6px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 22px;
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
      background: var(--accent);
      color: var(--accent-ink);
      padding: 12px 14px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
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
    .comparable {{
      border-top: 1px solid var(--line);
      padding: 12px 0;
    }}
    .comparable:first-of-type {{ border-top: 0; }}
    .comparable a {{ color: var(--accent); }}
    @media (max-width: 860px) {{
      main {{ grid-template-columns: 1fr; }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="brandmark">TRUNK</div>
  <main>
    <section class="panel">
      <h1>Luxury Price Appraisal</h1>
      <p class="lede">カテゴリを選び、商品写真と分かる範囲の情報を追加してください。</p>
      <form action="/appraisal" method="post" enctype="multipart/form-data">
        <label for="item_category">カテゴリ</label>
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

        <label for="item_images">商品写真</label>
        <input id="item_images" name="item_images" type="file" accept="image/*" multiple required>
        <p class="hint">正面、背面、角、内側/シリアル、金具、ダメージ箇所</p>

        <button type="submit">査定レンジを見る</button>
      </form>
    </section>
    <section class="panel">
      {result}
    </section>
  </main>
</body>
</html>"""


def render_select(name: str, options: list[str], selected: str) -> str:
    option_html = "\n".join(
        f'<option value="{escape(option)}"{selected_attr(option, selected)}>{escape(option)}</option>'
        for option in options
    )
    return f'<select id="{escape(name)}" name="{escape(name)}" required>{option_html}</select>'


def selected_attr(option: str, selected: str) -> str:
    return " selected" if option == selected else ""


def render_result(
    image_names: list[str],
    normalized_request: PriceEstimateRequest | None,
    estimate: PriceEstimateResponse | None,
    dify_draft: DifyDraft | None,
    dify_error: str | None,
    error: str | None,
) -> str:
    if error:
        return f"<h2>Estimate failed</h2><div class=\"warning\">{escape(error)}</div>"
    if not estimate or not normalized_request:
        return """<h2>How this works</h2>
<p>EcoAuc/Ecoring CSV data in Supabase is searched for comparable sold items. The service returns a market range, purchase-offer range, confidence, and evidence.</p>
<p class="small">Images are collected for condition review. Custom image training is intentionally deferred.</p>"""

    normalized = render_normalized_request(normalized_request)
    image_summary = render_image_summary(image_names)
    appraisal_note = render_appraisal_note(dify_draft, dify_error)
    market = render_price_range("推定市場価格", estimate.market_price_jpy)
    offer = render_price_range("買取提示レンジ", estimate.purchase_offer_jpy)
    missing = ", ".join(estimate.missing_inputs) if estimate.missing_inputs else "なし"
    comparables = "\n".join(render_comparable(item) for item in estimate.comparables[:5])
    return f"""
<h2>Estimate result</h2>
{appraisal_note}
{normalized}
{image_summary}
<div class="grid">
  {market}
  {offer}
  <div class="metric"><span>Confidence</span><b>{estimate.confidence:.0%}</b><small>Missing: {escape(missing)}</small></div>
</div>
<h2>Comparable sales</h2>
{comparables or '<p>No comparable sales found.</p>'}
"""


def render_appraisal_note(dify_draft: DifyDraft | None, dify_error: str | None) -> str:
    if dify_draft and dify_draft.text:
        body = "<br>".join(escape(line) for line in dify_draft.text.splitlines())
        return f"""<h2>査定コメント</h2>
<div class="warning">{body}</div>"""
    if dify_error:
        return f"""<div class="warning">{escape(dify_error)} 価格レンジは下記をご確認ください。</div>"""
    return ""


def render_normalized_request(request: PriceEstimateRequest) -> str:
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


def render_image_summary(image_names: list[str]) -> str:
    if not image_names:
        return """<div class="warning">画像は未アップロードです。正面、背面、角、内側/シリアル、金具、ダメージ箇所の写真を追加すると状態確認がしやすくなります。</div>"""
    names = ", ".join(escape(name) for name in image_names[:6])
    extra = "" if len(image_names) <= 6 else f" and {len(image_names) - 6} more"
    return f"""<div class="warning">画像 {len(image_names)} 件を受け取りました: {names}{extra}。Stage 1では価格計算には使わず、状態確認メモとして扱います。</div>"""


def render_price_range(label: str, price_range) -> str:
    if not price_range:
        return f"<div class=\"metric\"><span>{escape(label)}</span><b>-</b><small>No range</small></div>"
    return f"""<div class="metric">
  <span>{escape(label)}</span>
  <b>{price_range.mid:,}円</b>
  <small>{price_range.low:,}円 - {price_range.high:,}円</small>
</div>"""


def render_comparable(item) -> str:
    title = escape(item.title)
    url = item.item_url
    title_html = f"<a href=\"{escape(url)}\" target=\"_blank\" rel=\"noreferrer\">{title}</a>" if url else title
    sold_date = item.sold_date.isoformat() if item.sold_date else "unknown date"
    return f"""<div class="comparable">
  <strong>{item.price_jpy:,}円</strong> <span class="small">{escape(sold_date)} / rank {escape(item.rank or '-')} / score {item.score:.1f}</span>
  <div>{title_html}</div>
  <div class="small">{escape(', '.join(item.score_reasons[:3]))}</div>
</div>"""
