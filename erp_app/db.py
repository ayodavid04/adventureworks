"""Database access for the demo ERP. Every connection runs in UTC, so now() and the API agree."""

from __future__ import annotations

import os
import secrets
import sys
from contextlib import contextmanager
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import load_env  # noqa: E402

READONLY_USER = "aw_readonly"
_pool: ConnectionPool | None = None


def conninfo(user: str | None = None, password: str | None = None) -> str:
    e = load_env()
    from psycopg.conninfo import make_conninfo

    return make_conninfo(
        host=e["PGHOST"], port=e.get("PGPORT", "5432"), dbname=e["PGDATABASE"],
        user=user or e["PGUSER"], password=password or e["PGPASSWORD"],
        options="-c timezone=UTC", application_name="adventureworks-erp-demo",
    )


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(conninfo(), min_size=2, max_size=8, kwargs={"row_factory": dict_row}, open=True)
    return _pool


@contextmanager
def conn():
    with pool().connection() as c:
        yield c


def rows(sql: str, params=None) -> list[dict]:
    with conn() as c:
        return c.execute(sql, params).fetchall()


def one(sql: str, params=None) -> dict | None:
    with conn() as c:
        return c.execute(sql, params).fetchone()


def setup() -> None:
    """Create erp_app, an API key, move the ID sequences past the loaded data, set read-only grants."""
    with conn() as c:
        c.execute((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
        if not c.execute("select 1 from erp_app.api_keys where revoked_at is null").fetchone():
            c.execute("insert into erp_app.api_keys (api_key, label) values (%s, 'default')",
                      ("awk_" + secrets.token_urlsafe(24),))
        # The CSV load inserts explicit IDs, so the sequences were left at 1. Move them past the
        # highest ID, or the first simulated order would clash with Microsoft's order 1.
        for table, col in [("sales.salesorderheader", "salesorderid"),
                           ("sales.salesorderdetail", "salesorderdetailid"),
                           ("person.address", "addressid")]:
            c.execute(f"select setval(pg_get_serial_sequence('{table}', '{col}'), "
                      f"greatest((select max({col}) from {table}), 1))")
        # Never resume the simulator by surprise after a restart.
        c.execute("update erp_app.simulator_state set running = false where running")
        grant_readonly(c)


def readonly_exists(c) -> bool:
    return bool(c.execute("select 1 from pg_roles where rolname = %s", (READONLY_USER,)).fetchone())


def grant_readonly(c) -> None:
    """The read-only login is made by postgres (db/readonly_login.sql). Its grants are ours to give."""
    if not readonly_exists(c):
        return
    dbname = os.environ["PGDATABASE"]
    schemas = "person, humanresources, production, purchasing, sales"
    c.execute(f"grant connect on database {dbname} to {READONLY_USER}")
    c.execute(f"grant usage on schema {schemas} to {READONLY_USER}")
    c.execute(f"grant select on all tables in schema {schemas} to {READONLY_USER}")
    for s in schemas.split(", "):
        c.execute(f"alter default privileges in schema {s} grant select on tables to {READONLY_USER}")
    # erp_app holds the API key and webhook secrets, so the read-only login gets nothing there.


def api_key() -> str:
    return one("select api_key from erp_app.api_keys where revoked_at is null order by key_id limit 1")["api_key"]
