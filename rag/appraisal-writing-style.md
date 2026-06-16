# Appraisal Writing Style

Use this guide when writing `査定コメント` for customers or staff. The tone should be professional, cautious, concise, and easy to understand.

## Core Rules

- Do not mention internal tools, Dify, prompts, APIs, Supabase, RAG, or scraping.
- Do not invent prices, comparables, dates, ranks, or item details.
- Use the pricing API result as the only source of market price, purchase-offer range, confidence, and comparable sales.
- Use images only for visible product and condition signals.
- Use `brand-category-matrix.md` to decide which brand/category guidance applies.
- Use `brand-model-material-guide.md` for brand-specific model, material, color, hardware, and accessory wording.
- Use `category-appraisal-guide.md` for category-specific condition risks and missing-photo questions.
- Explain uncertainty clearly when data or photos are insufficient.
- Keep market price and purchase offer separate.

## Preferred Output Sections

Use these sections when enough information is available:

1. 推定市場価格
2. 買取提示レンジ
3. 信頼度
4. 主な比較対象
5. 画像から見える状態・リスク
6. 査定理由
7. 追加で確認したい情報

## Customer-Facing Tone

Use polite Japanese:

- 「現時点では」
- 「画像上確認できる範囲では」
- 「比較データ上は」
- 「最終査定は実物確認後となります」
- 「追加写真をいただけると精度が上がります」

Avoid overly strong claims:

- Avoid: 「確実に」
- Avoid: 「必ず」
- Avoid: 「本物です」
- Avoid: 「この価格で買取できます」

Better:

- 「目安として」
- 「可能性があります」
- 「確認が必要です」
- 「レンジは変動する場合があります」

## Price Wording

When the pricing API returns a range:

- 「比較落札データをもとに、推定市場価格は〇〇円から〇〇円前後、中間値は〇〇円です。」
- 「買取提示レンジは、再販リスクと事業マージンを考慮した目安です。」

## Confidence Thresholds

This is the single source of truth for mapping the pricing API output to confidence wording. Other guides reference this section instead of redefining bands.

The pricing API returns `confidence` as a number between `0.0` and `1.0`. Map it as:

- `confidence >= 0.7` -> high confidence wording.
- `0.4 <= confidence < 0.7` -> medium confidence wording.
- `0 < confidence < 0.4` -> low confidence wording.
- `comparable_count == 0`, or `market_price_jpy` is `null`, or `confidence == 0` -> use the no comparable sales wording and do not present an automatic range.

Treat `comparable_count == 0` / `market_price_jpy == null` as the authoritative no-data signal even if a confidence number is present.

When confidence is high:

- 「比較対象が複数確認できるため、現時点の推定信頼度は比較的高めです。」

When confidence is medium:

- 「比較対象はありますが、素材・サイズ・状態差により変動余地があります。」

When confidence is low:

- 「比較対象が限定的なため、レンジは参考値として扱い、実物確認後の調整が必要です。」

When no comparable sales are found:

- 「該当条件に近い比較落札データが不足しているため、現時点では価格レンジの提示を控えます。」
- 「ブランド、型番、サイズ、素材、付属品、状態写真を追加いただけると確認しやすくなります。」
- 「自動レンジではなく、スタッフ確認を前提とした参考コメントとしてご案内します。」

## Image Wording

When images are uploaded:

- 「画像上は、角スレ・金具小傷・型崩れの有無を中心に確認しました。」
- 「画像だけでは判断が難しいため、内側・シリアル/ICプレート・金具・四つ角の追加確認が必要です。」

When images are missing:

- 「画像確認ができていないため、状態ランクは仮の扱いです。」
- 「正面、背面、四つ角、内側、シリアル/ICプレート、金具、ダメージ箇所の写真をご共有ください。」

## Comparable Sales Wording

Mention comparables in plain language:

- 「主な比較対象として、同ブランド・同カテゴリ・近い形状の落札例を参照しています。」
- 「完全一致ではないため、素材・サイズ・状態差を考慮してレンジで提示しています。」

## Staff-Facing Notes

For staff, include concise risk flags:

- 「真贋確認: 必要」
- 「状態確認: 角スレ、金具、内側汚れ」
- 「追加確認: 付属品、購入時期、シリアル/IC」
- 「価格注意: 比較対象少、レンジ広め」
