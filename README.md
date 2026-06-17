# auction-price-checker-ai

Stage 1 no-training price estimator for luxury appraisal workflows.

This service reads normalized EcoAuc/Ecoring auction sales from Supabase Postgres and exposes a FastAPI endpoint that returns comparable-sales price ranges.

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

Use `on conflict (item_id) do update` so repeated scraper runs are safe and the pricing service always sees the latest normalized data.

## Run API

```sh
uvicorn luxury_price_ai.api:app --reload
```

Health check:

```sh
curl http://127.0.0.1:8000/health
```

Sample price estimate:

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

- Filters comparable sales by brand/category.
- Scores by shape, rank similarity, shared CHANEL title tokens, title overlap, and recency.
- Returns p25/median/p75 market range.
- Applies margin/risk discount separately for purchase-offer range.
- Returns comparable rows with score reasons for appraiser review.

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
PRICE_MARGIN_RATE=0.25
PRICE_RISK_DISCOUNT_RATE=0.05
DIFY_API_KEY=app-xxxxxxxxxxxxxxxx
DIFY_BASE_URL=https://api.dify.ai/v1
DIFY_USER=luxury-price-appraisal-web
```

`/health` is public for Render health checks. `/price-estimate` requires:

```http
X-API-Key: <APP_API_KEY>
```

After deploy, configure Dify's HTTP request node:

- Method: `POST`
- URL: `https://<render-service>.onrender.com/price-estimate`
- Header: `X-API-Key: <APP_API_KEY>`
- Header: `content-type: application/json`

## Dify Behind the Custom Form

The public `/appraisal` form is owned by this repo for a cleaner TRUNK-style intake UX. After the deterministic price estimate is computed, the server calls Dify when `DIFY_API_KEY` is configured.

Expected Dify workflow inputs:

- `item_description`
- `item_category`
- `brand`
- `item_shape`
- `item_name`
- `item_color`
- `condition_status`
- `item_photos`

If Dify is not configured or the workflow call fails, `/appraisal` still returns the local deterministic estimate and comparable sales evidence.
