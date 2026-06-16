# Brand Category Matrix

Use this matrix to route appraisal reasoning by the same brand and category scope as the monthly EcoAuc exports. This is not a price table. Always use the pricing API for market range, purchase-offer range, confidence, and comparable sales.

## Export Brands

Supported default export brands:

- LOUIS VUITTON
- HERMES
- CHANEL
- Saint Laurent
- Balenciaga
- Dior
- GUCCI
- PRADA

Normalize common aliases before calling the pricing API:

- `LV`, `Louis Vuitton`, `ルイヴィトン` -> `LOUIS VUITTON`
- `Hermes`, `エルメス` -> `HERMES`
- `シャネル`, `Channel` -> `CHANEL`
- `YSL`, `サンローラン`, `Saint Laurent Paris` -> `Saint Laurent`
- `バレンシアガ` -> `Balenciaga`
- `ディオール`, `Christian Dior` -> `Dior`
- `グッチ` -> `GUCCI`
- `プラダ` -> `PRADA`

## Export Categories

Supported default export categories:

- watches
- bags
- precious-metals
- accessories
- small-goods
- ceramics
- cameras
- apparel
- shoes
- art
- furniture
- bicycles
- home-appliances
- hobbies
- sports
- instruments
- consumables
- games
- computers
- camping
- audio

For customer-facing Japanese labels, prefer:

- watches -> 時計
- bags -> ブランドバッグ / バッグ
- precious-metals -> 貴金属
- accessories -> アクセサリー
- small-goods -> 財布・小物
- ceramics -> 陶器・食器
- cameras -> カメラ
- apparel -> 服
- shoes -> スニーカー・靴
- art -> 美術品・骨董品
- furniture -> 家具
- bicycles -> 自転車
- home-appliances -> 家電
- hobbies -> ホビー
- sports -> スポーツ用品
- instruments -> 楽器
- consumables -> 消耗品
- games -> ゲーム
- computers -> パソコン・PC
- camping -> キャンプ用品
- audio -> オーディオ

## Matrix Rules

Use the brand row for brand-specific cues. Use the category column for condition and photo requirements. If a cell is weak or uncommon, do not force a model guess; ask for model name, size, material, serial/authenticity marker, and clearer photos.

| Brand | High-priority categories | Secondary categories | Default handling |
| --- | --- | --- | --- |
| LOUIS VUITTON | bags, small-goods, accessories, apparel, shoes | watches, art, hobbies | Extract line, canvas/leather, model, size, date code or IC, accessories. |
| HERMES | bags, small-goods, accessories, watches, apparel, shoes | precious-metals, art, ceramics | Extract model, leather, stamp, size, hardware, accessories. Specialist review for high-value items. |
| CHANEL | bags, small-goods, accessories, apparel, shoes, watches | precious-metals, art | Extract model, material, color, hardware, serial/IC, accessories. |
| Saint Laurent | bags, small-goods, accessories, apparel, shoes | watches | Extract model line, leather, hardware, logo condition, size. |
| Balenciaga | bags, apparel, shoes, small-goods, accessories | watches | Extract model line, leather/fabric, size, distressing vs damage. |
| Dior | bags, small-goods, accessories, apparel, shoes | watches, art, ceramics | Extract model line, Oblique/cannage/material, charms, embroidery condition. |
| GUCCI | bags, small-goods, accessories, apparel, shoes, watches | jewelry/precious-metals | Extract GG line, canvas/leather, hardware, serial tag, size. |
| PRADA | bags, small-goods, accessories, apparel, shoes | watches | Extract nylon/Saffiano/leather, triangle logo, model, size, card/accessories. |

## Category Escalation

Always suggest staff review when:

- watches, precious-metals, art, cameras, instruments, audio, computers, bicycles, or home-appliances have high value or technical condition uncertainty.
- a brand/category combination is outside the usual luxury resale focus.
- the pricing API has no comparable data or low confidence.
- authenticity markers are missing or unclear.
- photos conflict with user-provided condition.

## No Comparable Data

When the pricing API returns no comparables, do not invent a price from this matrix. Use wording like:

- 「近い比較落札データが不足しているため、自動レンジは参考値として扱えません。ブランド、カテゴリ、型番、サイズ、素材、状態写真を追加確認したうえでスタッフ査定を推奨します。」

