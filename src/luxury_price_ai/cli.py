from __future__ import annotations

import argparse
from pathlib import Path
import sys

from luxury_price_ai.config import get_settings
from luxury_price_ai.storage import DatabaseConfigError, DatabaseConnectionError, PostgresStore


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

    args = parser.parse_args()
    try:
        if args.command == "db-check":
            run_db_check()
        elif args.command == "migrate":
            run_migrate(Path(args.file))
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


if __name__ == "__main__":
    main()
