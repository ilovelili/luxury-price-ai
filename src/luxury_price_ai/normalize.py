from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from luxury_price_ai.models import AuctionSale


REQUIRED_COLUMNS = {
    "month",
    "itemId",
    "soldDate",
    "brand",
    "title",
    "priceJpy",
}


def iter_export_rows(path: Path) -> Iterator[dict[str, str]]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not csv_names:
                raise ValueError(f"{path} does not contain a CSV file")
            for name in csv_names:
                with archive.open(name) as handle:
                    text = io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")
                    yield from _iter_csv_reader(csv.DictReader(text), name)
        return

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from _iter_csv_reader(csv.DictReader(handle), str(path))


def _iter_csv_reader(reader: csv.DictReader, label: str) -> Iterator[dict[str, str]]:
    fieldnames = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - fieldnames
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(sorted(missing))}")
    yield from reader


def normalize_row(row: dict[str, str]) -> AuctionSale | None:
    item_id = clean(row.get("itemId"))
    brand = clean(row.get("brand")) or clean(row.get("brandQuery"))
    title = clean(row.get("title"))
    price = parse_int(row.get("priceJpy"))

    if not item_id or not brand or not title or price is None:
        return None

    return AuctionSale(
        item_id=item_id,
        brand=brand.upper(),
        category=clean(row.get("category")),
        shape=clean(row.get("shape")),
        rank=clean(row.get("rank")).upper() or None,
        title=title,
        sold_date=parse_date(row.get("soldDate")),
        price_jpy=price,
        item_url=clean(row.get("itemUrl")),
        image_url=clean(row.get("imageUrl")),
        auction=clean(row.get("auction")),
        source_month=clean(row.get("month")),
        raw_payload=dict(row),
    )


def load_sales(path: Path) -> list[AuctionSale]:
    sales = []
    for row in iter_export_rows(path):
        sale = normalize_row(row)
        if sale:
            sales.append(sale)
    return sales


def clean(value: str | None) -> str:
    return (value or "").strip()


def parse_int(value: str | None) -> int | None:
    digits = clean(value).replace(",", "")
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def parse_date(value: str | None) -> date | None:
    text = clean(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None
