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

- The default `/auction-analysis` UI shows auction-record analysis.
- The `/image-auction-analysis` UI combines image inspection, auction-record analysis, and automated price ranges in one staff-facing flow.
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
```

`/health` is public for Render health checks. `/auction-analysis` and `/price-estimate` require:

```http
X-API-Key: <APP_API_KEY>
```

If using the analysis endpoint from Dify or another tool, configure the HTTP request node:

- Method: `POST`
- URL: `https://<render-service>.onrender.com/auction-analysis`
- Header: `X-API-Key: <APP_API_KEY>`
- Header: `content-type: application/json`

## Custom Form

The public `/auction-analysis` form is owned by this repo for a cleaner TRUNK-style intake UX. It calls the local analysis flow and shows matching auction records, summary statistics, charts, and recent movement. `/image-auction-analysis` accepts uploaded photos, infers search conditions, and shows market/purchase price ranges with the same auction evidence. Image inspection remains available as an API for Dify/internal flows, but there is no separate image-check page in the staff UI.

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
