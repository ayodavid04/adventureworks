"""Smoke test for the demo ERP's REST API (run while the app is up on 4690).

    python scripts/check_api.py

Checks the key is required, then pages through every customer with keyset paging and confirms
no row is skipped or repeated even though thousands of customers share one modifieddate.
It only reads. It is a check of the demo system, not an extractor.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import connect  # noqa: E402

BASE = "http://127.0.0.1:4690/api/v1"


def get(path: str, key: str | None):
    req = urllib.request.Request(BASE + path, headers={"X-API-Key": key} if key else {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def main() -> int:
    with connect() as c:
        key = c.execute("select api_key from erp_app.api_keys where revoked_at is null order by key_id limit 1").fetchone()[0]
        n_customers = c.execute("select count(*) from sales.customer").fetchone()[0]
        biggest_tie = c.execute("select count(*) from sales.customer group by modifieddate order by 1 desc limit 1").fetchone()[0]

    status, _ = get("/customers?limit=1", None)
    print("no key            ->", status)
    status, _ = get("/customers?limit=1", "wrong")
    print("wrong key         ->", status)
    status, body = get("/customers?after_id=5", key)
    print("after_id alone    ->", status, body.get("detail", "")[:60])

    seen, pages, path = [], 0, "/customers?limit=1000"
    while True:
        status, body = get(path, key)
        assert status == 200, body
        seen += [r["id"] for r in body["data"]]
        pages += 1
        if not body["next"]:
            break
        nxt = body["next"]
        path = f"/customers?limit=1000&modified_since={nxt['modified_since']}&after_id={nxt['after_id']}"
    print(f"customers paged   -> {len(seen):,} rows in {pages} pages; database has {n_customers:,}; "
          f"unique {len(set(seen)):,}; biggest group sharing one modifieddate: {biggest_tie:,}")
    ok = len(seen) == len(set(seen)) == n_customers
    status, body = get("/sales-orders?limit=2", key)
    print("sales-orders      ->", status, "first order has", len(body["data"][0]["lines"]), "lines nested")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
