from __future__ import annotations

from datetime import date
import unittest

from luxury_price_ai.config import Settings
from luxury_price_ai.estimator import estimate_price
from luxury_price_ai.models import AuctionSale, PriceEstimateRequest


SETTINGS = Settings(
    database_url=None,
    margin_rate=0.25,
    risk_discount_rate=0.05,
    app_api_key=None,
    openai_api_key=None,
    openai_vision_model="test",
    dify_api_key=None,
    dify_base_url="https://example.test",
    dify_user="test",
)


def sale(
    item_id: str,
    title: str,
    price_jpy: int,
    *,
    rank: str = "AB",
    shape: str = "ショルダーバッグ",
) -> AuctionSale:
    return AuctionSale(
        item_id=item_id,
        brand="CHANEL",
        category="バッグ",
        shape=shape,
        rank=rank,
        title=title,
        sold_date=date(2026, 1, 1),
        price_jpy=price_jpy,
    )


class StrictEstimatorTest(unittest.TestCase):
    def test_uses_only_exact_or_close_comparables_for_price_range(self) -> None:
        request = PriceEstimateRequest(
            brand="CHANEL",
            category="バッグ",
            shape="ショルダーバッグ",
            rank="AB",
            title="CHANEL マトラッセ キャビアスキン 黒 ゴールド金具",
        )

        response = estimate_price(
            request,
            [
                sale("exact", "CHANEL マトラッセ キャビアスキン 黒 ゴールド金具", 300_000),
                sale("wrong-model", "CHANEL ボーイ ラムスキン 黒 ゴールド金具", 900_000),
                sale("wrong-rank", "CHANEL マトラッセ キャビアスキン 黒 ゴールド金具", 100_000, rank="C"),
                sale("wrong-shape", "CHANEL マトラッセ キャビアスキン 黒 ゴールド金具", 800_000, shape="トートバッグ"),
            ],
            SETTINGS,
        )

        self.assertEqual(response.qualified_comparable_count, 1)
        self.assertEqual(response.market_price_jpy.mid, 300_000)
        qualities = {item.item_id: item.match_quality for item in response.comparables}
        self.assertEqual(qualities["exact"], "exact")
        self.assertEqual(qualities["wrong-model"], "excluded")
        self.assertEqual(qualities["wrong-rank"], "excluded")
        self.assertEqual(qualities["wrong-shape"], "excluded")

    def test_returns_no_range_when_product_line_is_not_confirmed(self) -> None:
        request = PriceEstimateRequest(
            brand="CHANEL",
            category="バッグ",
            shape="ショルダーバッグ",
            rank="AB",
            title="CHANEL 黒 ゴールド金具",
        )

        response = estimate_price(
            request,
            [sale("candidate", "CHANEL マトラッセ キャビアスキン 黒 ゴールド金具", 300_000)],
            SETTINGS,
        )

        self.assertIsNone(response.market_price_jpy)
        self.assertIn("confirmed model/line", response.missing_inputs)
        self.assertEqual(response.comparables[0].match_quality, "weak")


if __name__ == "__main__":
    unittest.main()
