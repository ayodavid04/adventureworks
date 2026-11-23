"""Make this project's database login: a random password in .env, and the SQL to create it.

    python db/prepare_login.py

Writes two files, both kept out of git:
  .env            the connection settings, with a new random password
  db/setup.sql    three lines for YOU to run once as the postgres superuser (DBeaver or psql)

Nothing else in this project needs the superuser. Same pattern as the Merseyside project.
"""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
SQL = ROOT / "db" / "setup.sql"
DB, USER = "adventureworks_erp", "aw_erp"


def main() -> int:
    if ENV.exists():
        sys.exit(".env already exists. Delete it first if you really want a new password.")
    pw = secrets.token_urlsafe(24)  # letters, digits, - and _ only, so it's safe inside SQL quotes
    ENV.write_text(
        f"PGHOST=127.0.0.1\nPGPORT=5432\nPGDATABASE={DB}\nPGUSER={USER}\nPGPASSWORD={pw}\n",
        encoding="utf-8",
    )
    SQL.write_text(
        "-- Run once as the postgres superuser, connected to the default 'postgres' database.\n"
        "-- DBeaver: open this file, pick your local postgres connection, Execute script (Alt+X).\n"
        "-- psql:    psql -U postgres -f db/setup.sql\n"
        "-- It makes one login and one database it owns. It changes no other database or setting.\n"
        f"CREATE ROLE {USER} LOGIN PASSWORD '{pw}';\n"
        f"CREATE DATABASE {DB} OWNER {USER};\n"
        f"COMMENT ON DATABASE {DB} IS 'Microsoft AdventureWorks public sample data (fictional company). Portfolio practice, not client data.';\n",
        encoding="utf-8",
    )
    print("wrote .env and db/setup.sql (both are in .gitignore)")
    print("next: run db/setup.sql as postgres, then python scripts/load_source.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
