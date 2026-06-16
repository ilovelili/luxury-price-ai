# Purchase Offer Policy

Use this guide to explain the difference between market price and purchase offer. Do not calculate prices in the LLM. Use the pricing API as the source of truth.

## Core Rule

Market price and purchase offer are separate.

- Market price: estimated resale or auction market range based on comparable sales.
- Purchase offer: business purchase range after margin, resale risk, condition risk, fees, holding cost, and uncertainty.

## Never Do This

- Do not invent a purchase price.
- Do not promise a final purchase amount before staff review.
- Do not use RAG text as a price table.
- Do not override pricing API ranges unless staff manually changes the result.

## Explain Purchase Offer

Use wording like:

- 「買取提示レンジは、再販時の手数料、状態リスク、在庫リスク、事業マージンを考慮した目安です。」
- 「市場価格そのものではなく、買取可能性を考慮した提示レンジです。」
- 「実物確認後、状態・付属品・真贋確認により調整される場合があります。」

## Factors That Can Raise Offer

- Strong brand and popular model
- High demand color such as 黒 / ブラック
- Desirable brand/category material, such as キャビアスキン for some CHANEL bags, Togo/Epsom for some HERMES bags, Monogram/Damier for common LOUIS VUITTON items, or Saffiano for some PRADA items
- Good condition
- Complete accessories
- Recent comparable sales with stable prices
- Clear photos and matching item details

## Factors That Can Lower Offer

- Heavy corner wear
- Stains, discoloration, odor, sticky interior, peeling
- Shape collapse
- Hardware tarnish or plating wear
- Missing accessories
- Missing or unclear serial/IC/authenticity marker
- Low number of comparable sales
- Large spread between comparable sale prices
- Rare item with uncertain demand

## Confidence Language

Use the numeric bands defined in `appraisal-writing-style.md` (Confidence Thresholds) to decide which level applies. That section is the single source of truth for the `confidence` cutoffs and the no-comparable-data signal; the wording below is the purchase-offer phrasing for each level.

High confidence:

- 「比較対象が十分にあり、レンジの信頼度は高めです。」

Medium confidence:

- 「比較対象はありますが、状態・素材・サイズ差により調整余地があります。」

Low confidence:

- 「比較対象が限定的なため、提示レンジは参考値です。追加情報と実物確認後に調整が必要です。」

No comparable data:

- 「近い比較落札データが不足しているため、自動レンジの提示は控え、スタッフ確認を推奨します。」

## Manual Review Triggers

Route to staff review when:

- No comparable sales are found.
- Item may be rare, limited, vintage, or collaboration.
- Watch, jewelry, precious metal, or art category requires specialist review.
- Technical categories such as cameras, instruments, audio, computers, bicycles, and home appliances have uncertain operation status.
- Non-core categories such as furniture, consumables, games, camping, sports, ceramics, or hobbies have unclear resale policy or condition.
- Photos suggest heavy damage.
- Authenticity marker is missing or unclear.
- User input conflicts with image evidence.
- Price range is very wide or confidence is low.

## Staff-Facing Summary Format

Use this format when helpful:

- 市場価格: pricing API range
- 買取提示: pricing API purchase-offer range
- 信頼度: pricing API confidence
- 主な下振れ要因: condition/accessory/data risks
- 追加確認: photos, serial/IC, accessories, size, purchase timing
