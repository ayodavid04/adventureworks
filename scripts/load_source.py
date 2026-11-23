"""Build the "source system": load AdventureWorks into the project database, as the project login.

    python scripts/load_source.py            first load
    python scripts/load_source.py --reset    drop the AdventureWorks schemas and load again

Runs lorint's install.sql (read it first: data/download/postgres_port/install.sql) through psql,
from inside the CSV folder because the script's \\copy lines use relative paths. It creates the
five ERP schemas (person, humanresources, production, purchasing, sales), the short-name view
schemas (pe, hr, pr, pu, sa), a few domains in public, and two trusted extensions.

--reset drops only those AdventureWorks objects; any schemas you create yourself are kept.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import connect, load_env  # noqa: E402

CSV_DIR = ROOT / "data" / "download" / "csv"
INSTALL = ROOT / "data" / "download" / "postgres_port" / "install.sql"
SOURCE_SCHEMAS = ["person", "humanresources", "production", "purchasing", "sales", "pe", "hr", "pr", "pu", "sa"]
DOMAINS = ['"OrderNumber"', '"AccountNumber"', '"Flag"', '"NameStyle"', '"Name"', '"Phone"']


def find_psql() -> str:
    found = shutil.which("psql")
    if found:
        return found
    for v in ("17", "16", "15"):
        p = Path(rf"C:\Program Files\PostgreSQL\{v}\bin\psql.exe")
        if p.exists():
            return str(p)
    sys.exit("psql not found. Add C:\\Program Files\\PostgreSQL\\17\\bin to PATH.")


def main() -> int:
    if not INSTALL.exists() or not any(CSV_DIR.glob("*.csv")):
        sys.exit("Run python scripts/fetch_source.py first.")
    env = load_env()

    with connect(autocommit=True) as conn:
        exists = conn.execute(
            "select count(*) from information_schema.schemata where schema_name = any(%s)", (SOURCE_SCHEMAS,)
        ).fetchone()[0]
        if exists and "--reset" not in sys.argv:
            sys.exit("AdventureWorks is already loaded. Use --reset to drop it and load again.")
        if exists:
            print("dropping the AdventureWorks schemas (your own schemas are kept)")
            conn.execute("drop schema if exists " + ", ".join(SOURCE_SCHEMAS) + " cascade")
            conn.execute("drop domain if exists " + ", ".join(DOMAINS) + " cascade")
            conn.execute('drop extension if exists tablefunc, "uuid-ossp" cascade')

    print("loading AdventureWorks (Microsoft's public sample data), about a minute...")
    run_env = {**os.environ, "PGHOST": env["PGHOST"], "PGPORT": env["PGPORT"], "PGDATABASE": env["PGDATABASE"],
               "PGUSER": env["PGUSER"], "PGPASSWORD": env["PGPASSWORD"], "PGCLIENTENCODING": "UTF8"}
    result = subprocess.run(
        [find_psql(), "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(INSTALL)],
        cwd=CSV_DIR, env=run_env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    log = ROOT / "logs" / "load_source.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(result.stdout + "\n--- stderr ---\n" + result.stderr, encoding="utf-8")
    if result.returncode != 0:
        print(result.stderr[-3000:])
        sys.exit(f"install.sql failed (full output in {log.relative_to(ROOT)})")

    with connect() as conn:
        rows = conn.execute("""
            select n.nspname, count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where c.relkind = 'r' and n.nspname = any(%s) group by 1 order by 1""", (SOURCE_SCHEMAS,)).fetchall()
        orders = conn.execute("select count(*), min(orderdate)::date, max(orderdate)::date from sales.salesorderheader").fetchone()
    print("tables per schema:", ", ".join(f"{s} {n}" for s, n in rows), f"(total {sum(n for _, n in rows)})")
    print(f"sales orders: {orders[0]:,} from {orders[1]} to {orders[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
