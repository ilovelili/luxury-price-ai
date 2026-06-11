# AGENTS.md

## Project

This repository is for building an AI-assisted luxury appraisal flow for TRUNK-style online査定.

The goal is to use EcoAuc/Ecoring auction-price exports, item photos, and user-submitted metadata to produce:

- estimated market price ranges,
- suggested purchase offer ranges,
- comparable auction examples,
- confidence/missing-input signals,
- staff-facing appraisal rationale.

The companion scraping/export repository is:

`/Users/min/Projects/src/github.com/ilovelili/auction-price-checker`

The first design note is:

`docs/luxury-price-ai-flow.md`

## Core Direction

Use Dify as the workflow/orchestration layer, not as the core pricing model.

Dify should handle:

- appraisal intake flow,
- LLM extraction and normalization,
- image/question workflow,
- RAG over appraisal policy and internal guidance,
- calling backend tools,
- final staff-facing/customer-facing wording.

This repo should own:

- CSV/artifact ingestion,
- data normalization,
- comparable-item search,
- price range estimation,
- model evaluation,
- image embeddings and condition scoring,
- API endpoints Dify can call.

Do not upload all auction rows into Dify as plain knowledge chunks for numeric pricing. Numeric estimation should be done by a database/vector/model service with deterministic tests.

## Data Shape

Current EcoAuc CSV exports contain columns like:

- `month`
- `brandQuery`
- `itemId`
- `itemUrl`
- `soldDate`
- `brand`
- `title`
- `rank`
- `category`
- `shape`
- `priceJpy`
- `auction`
- `imageUrl`

Treat `rank` as a useful but noisy weak label for condition. Treat `imageUrl` as training/evidence material only after checking access, storage, and licensing constraints.

## Implementation Principles

- Start explainable: comparable retrieval and percentile ranges before custom ML.
- Keep price logic outside prompts where possible.
- Store enough evidence for every estimate: filters, comparables, weights, and generated rationale.
- Separate market estimate from purchase offer. Business margin/risk rules should be explicit.
- Prefer range outputs over single prices.
- Track confidence and missing inputs.
- Save human appraiser corrections for evaluation.
- Design APIs so Dify, TRUNK site, LINE flow, or admin tools can call them.

## Suggested MVP

1. Ingest CSV/ZIP exports into local storage.
2. Normalize brand, category, shape, rank, sold date, and price.
3. Parse title tokens for model/material/color/hardware/accessories.
4. Build `/price-estimate`:
   - retrieve comparable sales,
   - compute low/mid/high market range,
   - compute purchase-offer range,
   - return confidence and missing inputs.
5. Add Dify workflow on top:
   - extract structured fields,
   - call `/price-estimate`,
   - generate appraisal draft.
6. Add image embeddings/condition scoring after the structured MVP works.

## Code Style

- Prefer small, testable modules.
- Keep ingestion, parsing, retrieval, pricing, and API layers separate.
- Avoid embedding business rules inside long prompts.
- Use structured parsers for CSV/ZIP data.
- Add tests around price calculation, filters, and normalization.
- Do not commit credentials, EcoAuc login data, or downloaded private images.

## Verification

Before considering a change complete:

- Run relevant tests or a smoke command.
- Check sample ZIP ingestion if ingestion logic changed.
- Verify price estimates include comparable evidence.
- Confirm no secrets or private raw data were accidentally added.

## Language Notes

The product and data are Japanese/English mixed. Preserve Japanese auction/category/model terms where they carry appraisal meaning, for example:

- `バッグ`
- `ショルダーバッグ`
- `マトラッセ`
- `キャビアスキン`
- `ラムスキン`
- `ゴールド金具`

Use clear English for code and API names unless the source value itself is Japanese.
