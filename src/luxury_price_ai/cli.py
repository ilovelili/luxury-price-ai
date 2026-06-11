from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

from luxury_price_ai.config import get_settings
from luxury_price_ai.normalize import load_sales
from luxury_price_ai.storage import DatabaseConfigError, DatabaseConnectionError, PostgresStore
from luxury_price_ai.tokens import extract_tokens


def main() -> None:
    parser = argparse.ArgumentParser(prog="luxury-price-ai")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("db-check", help="Check DATABASE_URL connectivity.")

    migrate = subcommands.add_parser("migrate", help="Apply local SQL migration to Postgres.")
    migrate.add_argument(
        "--file",
        default="migrations/001_create_auction_sales.sql",
        help="Migration SQL path.",
    )

    import_cmd = subcommands.add_parser("import", help="Import an EcoAuc CSV or ZIP export.")
    import_cmd.add_argument("path", help="Path to .csv or .zip export.")
    import_cmd.add_argument("--dry-run", action="store_true", help="Parse and summarize only.")
    import_cmd.add_argument("--batch-size", type=int, default=500)

    args = parser.parse_args()
    try:
        if args.command == "db-check":
            run_db_check()
        elif args.command == "migrate":
            run_migrate(Path(args.file))
        elif args.command == "import":
            run_import(Path(args.path), dry_run=args.dry_run, batch_size=args.batch_size)
    except (DatabaseConfigError, DatabaseConnectionError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def run_migrate(path: Path) -> None:
    settings = get_settings()
    store = PostgresStore(settings.database_url or "")
    store.apply_migration(path)
    print(f"Applied migration: {path}")


def run_db_check() -> None:
    settings = get_settings()
    store = PostgresStore(settings.database_url or "")
    info = store.check_connection()
    print("Connected to database")
    print(f"  database={info['database']}")
    print(f"  user={info['user']}")
    print(f"  version={info['version'].splitlines()[0]}")


def run_import(path: Path, dry_run: bool, batch_size: int) -> None:
    sales = load_sales(path)
    print_summary(sales, path)
    if dry_run:
        return

    settings = get_settings()
    store = PostgresStore(settings.database_url or "")
    count = store.upsert_sales(sales, batch_size=batch_size)
    print(f"Upserted {count} auction sale rows")


def print_summary(sales, path: Path) -> None:
    ranks = Counter(sale.rank or "" for sale in sales)
    shapes = Counter(sale.shape or "" for sale in sales)
    prices = sorted(sale.price_jpy for sale in sales)

    print(f"Source: {path}")
    print(f"Parsed rows: {len(sales)}")
    if prices:
        print(f"Price min/median/max: {prices[0]} / {prices[len(prices) // 2]} / {prices[-1]}")
    print("Top ranks:", ", ".join(f"{rank or '(blank)'}={count}" for rank, count in ranks.most_common(8)))
    print("Top shapes:", ", ".join(f"{shape or '(blank)'}={count}" for shape, count in shapes.most_common(8)))

    if sales:
        sample = sales[0]
        print("Sample item:")
        print(f"  item_id={sample.item_id}")
        print(f"  title={sample.title}")
        print(f"  tokens={extract_tokens(sample.title).model_dump()}")


if __name__ == "__main__":
    main()
