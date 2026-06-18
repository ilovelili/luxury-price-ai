from __future__ import annotations

from datetime import date, timedelta

from luxury_price_ai.estimator import percentile, same_text
from luxury_price_ai.models import (
    AuctionAnalysisRequest,
    AuctionDailyPoint,
    AuctionAnalysisResponse,
    AuctionHistogramBin,
    AuctionMonthlyPoint,
    AuctionPriceStats,
    AuctionRecord,
    AuctionSale,
    AuctionTrend,
    AuctionWindowPoint,
)


TREND_PERIOD_DAYS = 7
DAILY_TREND_DAYS = 90
WINDOW_TREND_DAYS = 90


def analyze_auction_sales(
    request: AuctionAnalysisRequest,
    candidates: list[AuctionSale],
) -> AuctionAnalysisResponse:
    records = [
        sale
        for sale in candidates
        if sale.price_jpy > 0
        and matches_optional_text(request.shape, sale.shape)
        and matches_optional_text(request.rank, sale.rank)
    ]
    records.sort(key=lambda sale: sale.sold_date or date.min, reverse=True)
    display_records = records[: request.limit]

    return AuctionAnalysisResponse(
        filters={
            "brand": request.brand,
            "category": request.category,
            "shape": request.shape,
            "rank": request.rank,
            "sold_after": request.sold_after.isoformat() if request.sold_after else None,
        },
        stats=build_stats(records),
        trend=build_trend(records),
        histogram=build_histogram(records),
        monthly_trend=build_monthly_trend(records),
        daily_trend=build_daily_trend(records),
        window_trend=build_window_trend(records),
        record_count=len(records),
        records=[to_auction_record(sale) for sale in display_records],
    )


def matches_optional_text(request_value: str | None, sale_value: str | None) -> bool:
    return not request_value or same_text(request_value, sale_value)


def to_auction_record(sale: AuctionSale) -> AuctionRecord:
    return AuctionRecord(
        item_id=sale.item_id,
        sold_date=sale.sold_date,
        brand=sale.brand,
        title=sale.title,
        rank=sale.rank,
        category=sale.category,
        shape=sale.shape,
        price_jpy=sale.price_jpy,
        item_url=sale.item_url,
        image_url=sale.image_url,
        auction=sale.auction,
        source_month=sale.source_month,
    )


def build_stats(records: list[AuctionSale]) -> AuctionPriceStats:
    prices = sorted(sale.price_jpy for sale in records)
    if not prices:
        return AuctionPriceStats(
            count=0,
            average_jpy=None,
            median_jpy=None,
            p25_jpy=None,
            p75_jpy=None,
            min_jpy=None,
            max_jpy=None,
        )
    return AuctionPriceStats(
        count=len(prices),
        average_jpy=round(sum(prices) / len(prices)),
        median_jpy=percentile(prices, 0.50),
        p25_jpy=percentile(prices, 0.25),
        p75_jpy=percentile(prices, 0.75),
        min_jpy=prices[0],
        max_jpy=prices[-1],
    )


def build_histogram(records: list[AuctionSale], bin_count: int = 8) -> list[AuctionHistogramBin]:
    prices = [sale.price_jpy for sale in records]
    if not prices:
        return []
    min_price = min(prices)
    max_price = max(prices)
    if min_price == max_price:
        return [
            AuctionHistogramBin(
                label=format_price_band(min_price, max_price),
                min_jpy=min_price,
                max_jpy=max_price,
                count=len(prices),
            )
        ]

    step = max(1, (max_price - min_price + bin_count - 1) // bin_count)
    bins = [
        {"min": min_price + (step * index), "max": min_price + (step * (index + 1)) - 1, "count": 0}
        for index in range(bin_count)
    ]
    bins[-1]["max"] = max_price
    for price in prices:
        index = min((price - min_price) // step, bin_count - 1)
        bins[index]["count"] += 1

    return [
        AuctionHistogramBin(
            label=format_price_band(item["min"], item["max"]),
            min_jpy=item["min"],
            max_jpy=item["max"],
            count=item["count"],
        )
        for item in bins
    ]


def build_monthly_trend(records: list[AuctionSale]) -> list[AuctionMonthlyPoint]:
    by_month: dict[str, list[int]] = {}
    for sale in records:
        if not sale.sold_date:
            continue
        month = sale.sold_date.strftime("%Y-%m")
        by_month.setdefault(month, []).append(sale.price_jpy)

    points = []
    for month in sorted(by_month)[-12:]:
        prices = sorted(by_month[month])
        points.append(
            AuctionMonthlyPoint(
                month=month,
                count=len(prices),
                median_jpy=percentile(prices, 0.50),
                average_jpy=round(sum(prices) / len(prices)),
            )
        )
    return points


def build_daily_trend(records: list[AuctionSale]) -> list[AuctionDailyPoint]:
    dated_records = [sale for sale in records if sale.sold_date]
    if not dated_records:
        return []

    latest_date = max(sale.sold_date for sale in dated_records if sale.sold_date)
    start_date = latest_date - timedelta(days=DAILY_TREND_DAYS - 1)
    by_day: dict[date, list[int]] = {}
    for sale in dated_records:
        if not sale.sold_date or sale.sold_date < start_date:
            continue
        by_day.setdefault(sale.sold_date, []).append(sale.price_jpy)

    points = []
    for sold_date in sorted(by_day):
        prices = sorted(by_day[sold_date])
        points.append(
            AuctionDailyPoint(
                date=sold_date,
                count=len(prices),
                median_jpy=percentile(prices, 0.50),
                average_jpy=round(sum(prices) / len(prices)),
            )
        )
    return points


def build_window_trend(records: list[AuctionSale]) -> list[AuctionWindowPoint]:
    dated_records = [sale for sale in records if sale.sold_date]
    if not dated_records:
        return []

    latest_date = max(sale.sold_date for sale in dated_records if sale.sold_date)
    first_window_start = latest_date - timedelta(days=WINDOW_TREND_DAYS - 1)
    windows = []
    window_start = first_window_start
    while window_start <= latest_date:
        window_end = min(window_start + timedelta(days=TREND_PERIOD_DAYS - 1), latest_date)
        prices = sorted(
            sale.price_jpy
            for sale in dated_records
            if sale.sold_date and window_start <= sale.sold_date <= window_end
        )
        if prices:
            windows.append(
                AuctionWindowPoint(
                    start_date=window_start,
                    end_date=window_end,
                    label=f"{window_start.strftime('%m/%d')}-{window_end.strftime('%m/%d')}",
                    count=len(prices),
                    median_jpy=percentile(prices, 0.50),
                    average_jpy=round(sum(prices) / len(prices)),
                )
            )
        window_start = window_end + timedelta(days=1)
    return windows


def format_price_band(min_price: int, max_price: int) -> str:
    if min_price == max_price:
        return f"{min_price // 1000:,}k"
    return f"{min_price // 1000:,}k-{max_price // 1000:,}k"


def build_trend(records: list[AuctionSale]) -> AuctionTrend:
    dated_records = [sale for sale in records if sale.sold_date]
    if not dated_records:
        return empty_trend()

    latest_date = max(sale.sold_date for sale in dated_records if sale.sold_date)
    recent_start = latest_date - timedelta(days=TREND_PERIOD_DAYS)
    previous_start = recent_start - timedelta(days=TREND_PERIOD_DAYS)

    recent_prices = sorted(
        sale.price_jpy
        for sale in dated_records
        if sale.sold_date and recent_start < sale.sold_date <= latest_date
    )
    previous_prices = sorted(
        sale.price_jpy
        for sale in dated_records
        if sale.sold_date and previous_start < sale.sold_date <= recent_start
    )

    recent_median = percentile(recent_prices, 0.50) if recent_prices else None
    previous_median = percentile(previous_prices, 0.50) if previous_prices else None
    if recent_median is None or previous_median in (None, 0):
        return AuctionTrend(
            recent_period_days=TREND_PERIOD_DAYS,
            recent_count=len(recent_prices),
            previous_count=len(previous_prices),
            recent_median_jpy=recent_median,
            previous_median_jpy=previous_median,
            change_jpy=None,
            change_percent=None,
            direction="unknown",
        )

    change_jpy = recent_median - previous_median
    change_percent = round((change_jpy / previous_median) * 100, 1)
    return AuctionTrend(
        recent_period_days=TREND_PERIOD_DAYS,
        recent_count=len(recent_prices),
        previous_count=len(previous_prices),
        recent_median_jpy=recent_median,
        previous_median_jpy=previous_median,
        change_jpy=change_jpy,
        change_percent=change_percent,
        direction=trend_direction(change_percent),
    )


def trend_direction(change_percent: float) -> str:
    if change_percent >= 5:
        return "up"
    if change_percent <= -5:
        return "down"
    return "flat"


def empty_trend() -> AuctionTrend:
    return AuctionTrend(
        recent_period_days=TREND_PERIOD_DAYS,
        recent_count=0,
        previous_count=0,
        recent_median_jpy=None,
        previous_median_jpy=None,
        change_jpy=None,
        change_percent=None,
        direction="unknown",
    )
