# auction-price-checker-ai

Stage 1 no-training price estimator for luxury appraisal workflows.

This service imports EcoAuc/Ecoring CSV exports, stores normalized auction sales in Supabase Postgres, and exposes a FastAPI endpoint that returns comparable-sales price ranges.

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

## Import EcoAuc Export

Dry run against the sample ZIP:

```sh
luxury-price-ai import --dry-run /Users/min/Downloads/ecoauc-export-27178494880-chanel.zip
```

Import into Supabase:

```sh
luxury-price-ai import /Users/min/Downloads/ecoauc-export-27178494880-chanel.zip
```

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
