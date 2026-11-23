"""Shared bits: read .env and open a connection as the project login."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict:
    env_file = ROOT / ".env"
    if not env_file.exists():
        sys.exit("No .env yet. Run: python db/prepare_login.py, then run db/setup.sql as postgres.")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    return os.environ


def connect(autocommit: bool = False):
    import psycopg

    e = load_env()
    return psycopg.connect(
        host=e["PGHOST"], port=e.get("PGPORT", "5432"), dbname=e["PGDATABASE"],
        user=e["PGUSER"], password=e["PGPASSWORD"], autocommit=autocommit,
    )
