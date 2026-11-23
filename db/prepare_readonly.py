"""Make the read-only login that the ERP's Connect page hands out.

    python db/prepare_readonly.py

Adds AW_READONLY_PASSWORD to .env and writes db/readonly_login.sql (both in .gitignore).
Run db/readonly_login.sql once as postgres. The app then grants the login SELECT on the five
AdventureWorks schemas the next time it starts (the app's owner login owns those tables).
"""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
SQL = ROOT / "db" / "readonly_login.sql"
USER = "aw_readonly"


def main() -> int:
    if not ENV.exists():
        sys.exit("Run python db/prepare_login.py first.")
    env = ENV.read_text(encoding="utf-8")
    if "AW_READONLY_PASSWORD=" in env:
        pw = next(l.split("=", 1)[1].strip() for l in env.splitlines() if l.startswith("AW_READONLY_PASSWORD="))
    else:
        pw = secrets.token_urlsafe(24)
        ENV.write_text(env.rstrip("\n") + f"\nAW_READONLY_USER={USER}\nAW_READONLY_PASSWORD={pw}\n", encoding="utf-8")
    SQL.write_text(
        "-- Run once as the postgres superuser, connected to the default 'postgres' database.\n"
        "-- psql:    psql -U postgres -h 127.0.0.1 -d postgres -f db/readonly_login.sql\n"
        "-- It makes one login that can log in and nothing else. The ERP app grants it SELECT on\n"
        "-- the AdventureWorks schemas when it next starts. No other database or setting changes.\n"
        f"CREATE ROLE {USER} LOGIN PASSWORD '{pw}';\n",
        encoding="utf-8",
    )
    print("wrote db/readonly_login.sql and AW_READONLY_PASSWORD in .env (both in .gitignore)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
