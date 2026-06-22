# auction-price-checker-ai

Stage 1 auction sales analysis app for luxury appraisal workflows.

This service reads normalized EcoAuc/Ecoring auction sales from Supabase Postgres and exposes FastAPI endpoints for auction-record analysis. The main app starts from median, average, quartiles, recent movement, and matching sale records instead of AI-generated prices.

The primary ingestion path is direct Supabase upsert from the companion scraper/export repository:

```text
/Users/min/Projects/src/github.com/ilovelili/auction-price-checker
```

That repo writes auction rows directly into `public.auction_sales`. This repo does not import EcoAuc ZIP/CSV exports; it reads normalized rows from Supabase for comparable search and price estimation.

## Supabase Target

- Project id: `ipjilpsybkhhrquoingm`
- Project URL: `https://ipjilpsybkhhrquoingm.supabase.co`
- Session Pooler DB URL shape:

```sh
postgresql://postgres.ipjilpsybkhhrquoingm:YOUR-PASSWORD@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres
```

Do not commit the real password. Put it in `DATABASE_URL`.

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Edit `.env` and set the real `DATABASE_URL`.

Load env vars:

```sh
set -a
source .env
set +a
```

## Apply Schema

```sh
luxury-price-ai migrate
```

This applies `migrations/001_create_auction_sales.sql`, creating `public.auction_sales` with RLS enabled and no public read policy.

## Direct Supabase Ingestion

The companion `auction-price-checker` repo should normalize each EcoAuc row and upsert into `public.auction_sales` using the same column contract as this service:

| Source field | Supabase column | Notes |
| --- | --- | --- |
| `itemId` | `item_id` | Stable unique key; used for idempotent upserts. |
| `brand` or `brandQuery` | `brand` | Store uppercase normalized brand. |
| `category` | `category` | Preserve Japanese category names such as `バッグ`. |
| `shape` | `shape` | Preserve Japanese shape names such as `ショルダーバッグ`. |
| `rank` | `rank` | Uppercase auction condition rank; useful but noisy. |
| `title` | `title` | Required; used for token matching. |
| `soldDate` | `sold_date` | ISO date when available. |
| `priceJpy` | `price_jpy` | Integer JPY sale price. |
| `itemUrl` | `item_url` | Comparable evidence link. |
| `imageUrl` | `image_url` | Evidence/training pointer, subject to access/licensing checks. |
| `auction` | `auction` | Source auction label. |
| `month` | `source_month` | Export/search month. |
| full row | `raw_payload` | Original source row as JSONB for audit/debugging. |

Use `on conflict (item_id) do update` so repeated scraper runs are safe and the analysis service always sees the latest normalized data.

## Run API

```sh
uvicorn luxury_price_ai.api:app --reload
```

Health check:

```sh
curl http://127.0.0.1:8000/health
```

Sample auction analysis:

```sh
curl -X POST http://127.0.0.1:8000/auction-analysis \
  -H 'content-type: application/json' \
  -d '{
    "brand": "CHANEL",
    "category": "バッグ",
    "shape": "ショルダーバッグ",
    "rank": "AB",
    "title": "CHANEL マトラッセ キャビアスキン 黒 ゴールド金具",
    "limit": 50
  }'
```

Legacy price estimate:

```sh
curl -X POST http://127.0.0.1:8000/price-estimate \
  -H 'content-type: application/json' \
  -d '{
    "brand": "CHANEL",
    "category": "バッグ",
    "shape": "ショルダーバッグ",
    "rank": "AB",
    "title": "CHANEL マトラッセ キャビアスキン 黒 ゴールド金具",
    "limit": 20
  }'
```

## Stage 1 Behavior

- The default staff UI is `/image-auction-analysis`, titled Auction Sales Analysis.
- The single staff page combines optional image inspection, explicit auction-record filters, summary statistics, charts, and automated price ranges.
- Filters auction sales by explicit fields: brand/category from the database query, then shape/rank when provided.
- Returns matching auction records, average, median, p25/p75, min/max, histogram bins, current 7-day versus previous 7-day movement, and a 3-month line chart of 7-day median windows.
- Keeps `/price-estimate` available as a legacy deterministic comparable-sales endpoint.
- Image uploads can be used to infer search conditions for `/image-auction-analysis`; EcoAuc image URLs are shown as evidence links and are not downloaded or stored by this service.

No ML training or image downloading is included in Stage 1.

## Deploy on Render

This repo includes `render.yaml` for a Render Blueprint web service.

Recommended Render settings:

- Service type: Web Service
- Runtime: Python
- Plan: Starter
- Build command: `pip install -e .`
- Start command: `uvicorn luxury_price_ai.api:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

Required environment variables:

```sh
DATABASE_URL=postgresql://postgres.ipjilpsybkhhrquoingm:YOUR-PASSWORD@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres
APP_API_KEY=replace-with-a-long-random-secret
```

Optional legacy `/price-estimate` environment variables:

```sh
PRICE_MARGIN_RATE=0.25
PRICE_RISK_DISCOUNT_RATE=0.05
```

Optional `/image-inspection` environment variables:

```sh
OPENAI_API_KEY=sk-replace-with-your-openai-api-key
OPENAI_VISION_MODEL=gpt-5.5
GEMINI_API_KEY=replace-with-your-gemini-api-key
GEMINI_VISION_MODEL=gemini-3.5-flash
```

When `GEMINI_API_KEY` is set, `/image-inspection/analyze` and
`/image-inspection/analyze-dify` run OpenAI Vision and Gemini Vision, then merge
the results. Matching model/line candidates are normalized into canonical names
such as `CHANEL 22`, `CHANEL Classic Flap`, or `CHANEL Classic Double Flap`.
If Gemini is not configured, the endpoints fall back to OpenAI-only inspection.

`/health` is public for Render health checks. JSON API endpoints such as `/auction-analysis`, `/image-auction-analysis`, and `/price-estimate` require:

```http
X-API-Key: <APP_API_KEY>
```

If using the text-only analysis endpoint from Dify or another tool, configure the HTTP request node:

- Method: `POST`
- URL: `https://<render-service>.onrender.com/auction-analysis`
- Header: `X-API-Key: <APP_API_KEY>`
- Header: `content-type: application/json`

For Dify image intake, configure the HTTP request node to call:

- Method: `POST`
- URL: `https://<render-service>.onrender.com/image-inspection/analyze-dify`
- Header: `X-API-Key: <APP_API_KEY>`
- Header: `content-type: application/json`
- Body: pass Dify file variables in `item_images`, `item_photos`, or `files`

The backend handles the OpenAI + Gemini consensus. Dify does not need to call
Gemini directly unless you want a fully custom workflow branch inside Dify.

The `/image-auction-analysis` result also calls the configured Dify workflow
after backend pricing completes. The backend sends the user inputs, uploaded
photos, inferred request, price estimate, auction stats, comparable auction
records, missing inputs, and image inspection summary to Dify. Dify should use
its knowledge base/RAG documents to produce the final staff-facing appraisal
rationale shown under `査定コメント`.

Recommended Dify workflow input variables:

- `item_description`
- `item_category`
- `brand`
- `item_shape`
- `item_name`
- `item_color`
- `condition_status`
- `item_photos`
- `appraisal_context`
- `market_price_range`
- `purchase_offer_range`
- `price_basis`
- `confidence`
- `missing_inputs`
- `comparable_count`
- `qualified_comparable_count`

## Custom Form

The public `/image-auction-analysis` form is owned by this repo for a cleaner TRUNK-style intake UX. It accepts optional uploaded photos, infers search conditions when photos are present, and shows matching auction records, summary statistics, charts, recent movement, and market/purchase price ranges. Image inspection remains available as an API for Dify/internal flows, but there is no separate image-check page in the staff UI.

Current form inputs:

- `item_description`
- `item_category`
- `brand`
- `item_shape`
- `item_name`
- `item_color`
- `condition_status`
- `item_photos`

Images are received for staff review context. In `/image-auction-analysis`, image-derived brand/model/condition signals are used to fill missing search conditions before the auction analysis and price-range calculation.

For `/image-auction-analysis`, the recommended upload is 6 photos:

- Front full view
- Back full view
- Logo, stamp, or visible brand mark
- Corners, bottom, and edges
- Hardware, zipper, chain, or clasp
- Interior, serial/stamp, and visible damage areas

Fewer photos are accepted, but missing angles are returned as part of the inspection result.
