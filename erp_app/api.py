"""REST API v1: what an extractor pulls from.

Every list endpoint takes the same three parameters:
  modified_since  ISO 8601 time (UTC). Rows with modified_at >= this.
  after_id        with modified_since, continue after this row: (modified_at, id) > (modified_since, after_id)
  limit           rows per page, default 500, max 1000

Rows always come oldest change first, then by id. Each page returns `next`: pass its
modified_since and after_id back to get the next page. A page shorter than `limit` means you've
caught up. Send the key in an X-API-Key header.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from . import db
from .datasets import CUSTOMERS, INVENTORY, ORDER_LINES, PRODUCTS, SALES_ORDERS, clean, parse_ts

router = APIRouter(prefix="/api/v1")


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    if not x_api_key or not db.one(
        "select 1 from erp_app.api_keys where api_key = %s and revoked_at is null", (x_api_key,)
    ):
        raise HTTPException(status_code=401, detail="Missing or wrong X-API-Key header")


def page(request: Request, base_sql: str, modified_since: str | None, after_id: int | None, limit: int):
    if after_id is not None and not modified_since:
        raise HTTPException(400, "after_id needs modified_since too: pass both values from the last page's `next`")
    try:
        since = parse_ts(modified_since)
    except ValueError:
        raise HTTPException(400, "modified_since must be an ISO 8601 time, e.g. 2025-06-01T00:00:00Z")
    where, params = "", {"limit": limit}
    if since is not None and after_id is not None:
        where = "where (modified_at, id) > (%(since)s, %(after_id)s)"
        params |= {"since": since, "after_id": after_id}
    elif since is not None:
        where = "where modified_at >= %(since)s"
        params["since"] = since
    data = db.rows(f"select * from ({base_sql}) x {where} order by modified_at, id limit %(limit)s", params)
    nxt = None
    if len(data) == limit:
        last = clean(data[-1])
        nxt = {"modified_since": last["modified_at"], "after_id": last["id"]}
    out = {"count": len(data), "limit": limit, "next": nxt, "data": [clean(r) for r in data]}
    if nxt:
        out["next_url"] = f"{request.url.scheme}://{request.url.netloc}{request.url.path}?{urlencode({**nxt, 'limit': limit})}"
    return out, data


Since = Query(default=None, description="ISO 8601 UTC time; rows changed at or after it")
After = Query(default=None, description="Continue after this id (needs modified_since)")
Limit = Query(default=500, ge=1, le=1000)


@router.get("/sales-orders", dependencies=[Depends(require_key)])
def sales_orders(request: Request, modified_since: str | None = Since, after_id: int | None = After, limit: int = Limit):
    out, data = page(request, SALES_ORDERS, modified_since, after_id, limit)
    ids = [r["id"] for r in data]
    lines: dict[int, list] = {}
    if ids:
        for ln in db.rows(f"select * from ({ORDER_LINES}) x where sales_order_id = any(%s) order by id", (ids,)):
            lines.setdefault(ln["sales_order_id"], []).append(clean(ln))
    for o in out["data"]:
        o["lines"] = lines.get(o["id"], [])
    return out


@router.get("/sales-orders/{order_id}", dependencies=[Depends(require_key)])
def sales_order(order_id: int):
    h = db.one(f"select * from ({SALES_ORDERS}) x where id = %s", (order_id,))
    if not h:
        raise HTTPException(404, "No such order")
    o = clean(h)
    o["lines"] = [clean(r) for r in db.rows(f"select * from ({ORDER_LINES}) x where sales_order_id = %s order by id", (order_id,))]
    return o


@router.get("/customers", dependencies=[Depends(require_key)])
def customers(request: Request, modified_since: str | None = Since, after_id: int | None = After, limit: int = Limit):
    return page(request, CUSTOMERS, modified_since, after_id, limit)[0]


@router.get("/products", dependencies=[Depends(require_key)])
def products(request: Request, modified_since: str | None = Since, after_id: int | None = After, limit: int = Limit):
    return page(request, PRODUCTS, modified_since, after_id, limit)[0]


@router.get("/inventory", dependencies=[Depends(require_key)])
def inventory(request: Request, modified_since: str | None = Since, after_id: int | None = After, limit: int = Limit):
    """id here is product_id * 1000 + location_id, so each product-location row has one number."""
    return page(request, INVENTORY, modified_since, after_id, limit)[0]
