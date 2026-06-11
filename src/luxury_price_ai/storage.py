from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path
import socket
from typing import Any

from luxury_price_ai.models import AuctionSale


class DatabaseConfigError(RuntimeError):
    pass


class DatabaseConnectionError(RuntimeError):
    pass


def require_database_url(database_url: str | None) -> str:
    if not database_url:
        raise DatabaseConfigError(
            "DATABASE_URL is required. Use the Supabase direct connection string, "
            "for example postgresql://postgres.ipjilpsybkhhrquoingm:YOUR-PASSWORD@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres"
        )
    return database_url


class PostgresStore:
    def __init__(self, database_url: str):
        self.database_url = require_database_url(database_url)

    def apply_migration(self, migration_path: Path) -> None:
        import psycopg

        sql = migration_path.read_text(encoding="utf-8")
        try:
            with psycopg.connect(self.database_url) as conn:
                conn.execute(sql)
        except psycopg.OperationalError as exc:
            raise DatabaseConnectionError(explain_connection_error(exc)) from exc

    def upsert_sales(self, sales: Iterable[AuctionSale], batch_size: int = 500) -> int:
        import psycopg
        from psycopg.types.json import Jsonb

        rows = []
        total = 0
        try:
            with psycopg.connect(self.database_url) as conn:
                with conn.cursor() as cur:
                    for sale in sales:
                        rows.append(_sale_params(sale, Jsonb))
                        if len(rows) >= batch_size:
                            cur.executemany(UPSERT_SQL, rows)
                            total += len(rows)
                            rows = []
                    if rows:
                        cur.executemany(UPSERT_SQL, rows)
                        total += len(rows)
        except psycopg.OperationalError as exc:
            raise DatabaseConnectionError(explain_connection_error(exc)) from exc
        return total

    def check_connection(self) -> dict[str, str]:
        import psycopg

        try:
            with psycopg.connect(self.database_url) as conn:
                row = conn.execute(
                    "select current_database(), current_user, version()"
                ).fetchone()
        except psycopg.OperationalError as exc:
            raise DatabaseConnectionError(explain_connection_error(exc)) from exc

        return {
            "database": row[0],
            "user": row[1],
            "version": row[2],
        }

    def fetch_candidates(
        self,
        brand: str,
        category: str | None,
        sold_after: date | None,
        max_rows: int = 3000,
    ) -> list[AuctionSale]:
        import psycopg
        from psycopg.rows import dict_row

        clauses = ["upper(brand) = upper(%(brand)s)"]
        params: dict[str, Any] = {"brand": brand, "limit": max_rows}

        if category:
            clauses.append("category = %(category)s")
            params["category"] = category
        if sold_after:
            clauses.append("(sold_date is null or sold_date >= %(sold_after)s)")
            params["sold_after"] = sold_after

        where_sql = " and ".join(clauses)
        sql = f"""
            select
              item_id, brand, category, shape, rank, title, sold_date, price_jpy,
              item_url, image_url, auction, source_month, raw_payload
            from public.auction_sales
            where {where_sql}
            order by sold_date desc nulls last
            limit %(limit)s
        """

        try:
            with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
                rows = conn.execute(sql, params).fetchall()
        except psycopg.OperationalError as exc:
            raise DatabaseConnectionError(explain_connection_error(exc)) from exc
        return [AuctionSale.model_validate(dict(row)) for row in rows]


UPSERT_SQL = """
insert into public.auction_sales (
  item_id, brand, category, shape, rank, title, sold_date, price_jpy,
  item_url, image_url, auction, source_month, raw_payload
) values (
  %(item_id)s, %(brand)s, %(category)s, %(shape)s, %(rank)s, %(title)s,
  %(sold_date)s, %(price_jpy)s, %(item_url)s, %(image_url)s, %(auction)s,
  %(source_month)s, %(raw_payload)s
)
on conflict (item_id) do update set
  brand = excluded.brand,
  category = excluded.category,
  shape = excluded.shape,
  rank = excluded.rank,
  title = excluded.title,
  sold_date = excluded.sold_date,
  price_jpy = excluded.price_jpy,
  item_url = excluded.item_url,
  image_url = excluded.image_url,
  auction = excluded.auction,
  source_month = excluded.source_month,
  raw_payload = excluded.raw_payload
"""


def _sale_params(sale: AuctionSale, jsonb_factory: Any) -> dict[str, Any]:
    data = sale.model_dump()
    data["raw_payload"] = jsonb_factory(sale.raw_payload)
    return data


def explain_connection_error(exc: Exception) -> str:
    message = str(exc)
    if "could not translate host name" in message or "failed to resolve host" in message:
        return (
            "Could not resolve the Supabase database hostname. If you are using the "
            "direct db.<project-ref>.supabase.co connection, confirm the project ref "
            "and network DNS. Supabase direct connections are IPv6-first; if your "
            "network cannot use that endpoint, copy the Session Pooler connection "
            "string from Supabase Dashboard > Connect and use that as DATABASE_URL."
        )
    if "password authentication failed" in message:
        return (
            "Postgres rejected the password. Reset or confirm the database password "
            "in Supabase Dashboard > Project Settings > Database, then update DATABASE_URL."
        )
    if "Network is unreachable" in message or "No route to host" in message:
        return (
            "The database host resolved, but the network route is unavailable. "
            "For Supabase direct connections this often means the network cannot reach "
            "IPv6. Use the Supabase Session Pooler connection string instead."
        )
    return f"Database connection failed: {message}"


def resolve_database_host(host: str) -> list[str]:
    return sorted({addr[4][0] for addr in socket.getaddrinfo(host, 5432)})
