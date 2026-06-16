# RAG Guidance Docs

These Markdown files are the appraisal policy and reference knowledge used by the Dify workflow when it writes `査定コメント`. They are not loaded by this repo's code; they are registered in Dify's knowledge base and retrieved at appraisal time.

Numeric pricing is never produced from these docs. The pricing API (`src/luxury_price_ai/estimator.py`) is the only source of market price, purchase-offer range, confidence, and comparable sales. These docs only control how that output is explained.

## Files

| File | Purpose |
| --- | --- |
| `appraisal-writing-style.md` | Tone, output sections, price/confidence/image wording. Owns the confidence threshold table. |
| `purchase-offer-policy.md` | Market price vs purchase offer, factors, manual-review triggers. |
| `condition-rank-guide.md` | Condition rank vocabulary and wording (S/N/A/AB/B/BC/C/D/F). |
| `brand-category-matrix.md` | Brand/category routing, alias normalization, values to send to the pricing API. |
| `brand-model-material-guide.md` | Brand-specific model, material, color, and hardware cues. |
| `category-appraisal-guide.md` | Category-specific condition risks and missing-input questions. |
| `photo-review-checklist.md` | Required photos and condition signals by category. |

## Keep In Sync With The Pricing API

When the pricing API response schema changes, update these docs together:

- `confidence` is a `0.0`–`1.0` float. The bands are defined once in `appraisal-writing-style.md` (Confidence Thresholds). Do not redefine them elsewhere.
- The rank set is `S, N, A, AB, B, BC, C, D, F` (see `condition-rank-guide.md`) and must match `RANK_ORDER` in `estimator.py`.
- `category` and `shape` sent to the API are the Japanese auction values (`バッグ`, `ショルダーバッグ`), not the English export slugs. `brand` is the normalized English name. See `brand-category-matrix.md`.
- No-comparable-data is signalled by `comparable_count == 0` or `market_price_jpy == null`.

## Always-On Policy vs Retrieved Reference

Two kinds of content live here:

- **Always-on policy** — must apply to every appraisal: the safety rules in `appraisal-writing-style.md` (do not name internal tools, do not invent prices, do not guarantee authenticity), the market-vs-offer rule, and the confidence thresholds.
- **Retrieved reference** — only relevant to a specific item: per-brand cues (`brand-model-material-guide.md`), per-category inspection (`category-appraisal-guide.md`), and photo requirements (`photo-review-checklist.md`).

Recommendation: put always-on policy in the Dify system prompt so a retrieval miss can never drop a safety rule, and keep only the per-brand / per-category reference in the retrieved knowledge base.

## Chunking

For the brand and category reference files, set Dify's chunk delimiter to the `##` heading boundary so one chunk equals one brand or one category. Token-length chunking can split a brand mid-section and mix it with another brand at retrieval time.

## Known Duplication To Consolidate

The same content currently appears in several files. Each topic should have one owner and be referenced elsewhere:

- Confidence wording: `appraisal-writing-style.md` + `purchase-offer-policy.md` (thresholds now centralized in `appraisal-writing-style.md`).
- No-comparable-data wording: `appraisal-writing-style.md`, `brand-category-matrix.md`, `purchase-offer-policy.md`.
- Staff-review triggers: `brand-category-matrix.md`, `category-appraisal-guide.md`, `purchase-offer-policy.md`.
- Photo-angle lists: `condition-rank-guide.md`, `category-appraisal-guide.md`, `photo-review-checklist.md`.
