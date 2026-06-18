from __future__ import annotations

from datetime import date
import unittest

from luxury_price_ai.analysis import analyze_auction_sales
from luxury_price_ai.models import AuctionAnalysisRequest, AuctionSale


def sale(
    item_id: str,
    price_jpy: int,
    sold_date: date,
    *,
    shape: str = "ショルダーバッグ",
    rank: str = "AB",
) -> AuctionSale:
    return AuctionSale(
        item_id=item_id,
        brand="CHANEL",
        category="バッグ",
        shape=shape,
        rank=rank,
        title="CHANEL マトラッセ キャビアスキン 黒",
        sold_date=sold_date,
        price_jpy=price_jpy,
    )


class AuctionAnalysisTest(unittest.TestCase):
    def test_analyzes_explicitly_filtered_records(self) -> None:
        response = analyze_auction_sales(
            AuctionAnalysisRequest(
                brand="CHANEL",
                category="バッグ",
                shape="ショルダーバッグ",
                rank="AB",
                limit=2,
            ),
            [
                sale("1", 100_000, date(2026, 6, 1)),
                sale("2", 200_000, date(2026, 5, 1)),
                sale("3", 300_000, date(2026, 4, 1)),
                sale("shape-mismatch", 900_000, date(2026, 6, 1), shape="トートバッグ"),
                sale("rank-mismatch", 800_000, date(2026, 6, 1), rank="B"),
                sale("zero", 0, date(2026, 6, 1)),
            ],
        )

        self.assertEqual(response.record_count, 3)
        self.assertEqual(len(response.records), 2)
        self.assertEqual(response.stats.count, 3)
        self.assertEqual(response.stats.average_jpy, 200_000)
        self.assertEqual(response.stats.median_jpy, 200_000)
        self.assertEqual(response.stats.p25_jpy, 150_000)
        self.assertEqual(response.stats.p75_jpy, 250_000)
        self.assertEqual(sum(item.count for item in response.histogram), 3)
        self.assertEqual(response.monthly_trend[-1].month, "2026-06")
        self.assertEqual(response.daily_trend[-1].date, date(2026, 6, 1))
        self.assertTrue(response.window_trend)

    def test_reports_recent_median_movement(self) -> None:
        response = analyze_auction_sales(
            AuctionAnalysisRequest(brand="CHANEL", category="バッグ", shape="ショルダーバッグ"),
            [
                sale("recent-1", 200_000, date(2026, 6, 1)),
                sale("recent-2", 220_000, date(2026, 5, 31)),
                sale("previous-1", 100_000, date(2026, 5, 24)),
                sale("previous-2", 120_000, date(2026, 5, 23)),
            ],
        )

        self.assertEqual(response.trend.recent_period_days, 7)
        self.assertEqual(response.trend.recent_count, 2)
        self.assertEqual(response.trend.previous_count, 2)
        self.assertEqual(response.trend.recent_median_jpy, 210_000)
        self.assertEqual(response.trend.previous_median_jpy, 110_000)
        self.assertEqual(response.trend.change_jpy, 100_000)
        self.assertEqual(response.trend.direction, "up")

    def test_reports_multiple_7_day_windows(self) -> None:
        response = analyze_auction_sales(
            AuctionAnalysisRequest(brand="CHANEL", category="バッグ", shape="ショルダーバッグ"),
            [
                sale("window-1", 100_000, date(2026, 5, 10)),
                sale("window-2", 200_000, date(2026, 5, 17)),
                sale("window-3", 300_000, date(2026, 5, 24)),
                sale("window-4", 400_000, date(2026, 5, 31)),
            ],
        )

        self.assertGreaterEqual(len(response.window_trend), 4)
        self.assertEqual(response.window_trend[-1].median_jpy, 400_000)


if __name__ == "__main__":
    unittest.main()
