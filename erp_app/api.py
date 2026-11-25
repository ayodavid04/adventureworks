"""REST API v1: what an extractor pulls from.

Every list endpoint takes the same three parameters:
  modified_since  ISO 8601 time (UTC). Rows with modified_at >= this.
  after_id        with modified_since, continue after this row: (modified_at, id) > (modified_since, after_id)
  limit           rows per page, default 500, max 1000

Rows always come oldest change first, then by id. Each page returns `next`: pass its
modified_since and after_id back to get the next page. A page shorter than `limit` means you've
caught up. Send the key in an X-API-Key header.\n"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import APIKeyHeader

from . import db
from .datasets import CUSTOMERS, INVENTORY, ORDER_LINES, PRODUCTS, SALES_ORDERS, clean, parse_ts

router = APIRouter(prefix="/api/v1")

# A security scheme (not a plain header) so the docs page gets an Authorize button: paste the key once
# and every Try it out sends it.
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Copy the key from the ERP's Integrations page (http://localhost:4690/integrations) and paste it here.",
)


def require_key(x_api_key: str | None = Security(api_key_header)) -> None:
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


Since = Query(
    default=None,
    description="Only rows changed at or after this time (UTC), e.g. 2025-06-01T00:00:00Z. "
    "Leave empty for everything. For page 2, copy `next.modified_since` from the last answer.",
)
After = Query(
    default=None,
    description="For page 2 onwards: copy `next.after_id` from the last answer. Needs modified_since too.",
)
Limit = Query(default=500, ge=1, le=1000, description="Rows per page. Try 5 while you're learning, so the answer fits on screen.")

PAGING_HINT = (
    "\n\n**Try it:** Try it out, set limit to 5, Execute. 200 = worked, 401 = click Authorize and paste the key."
    "\n\n**Next page:** at the bottom of the answer, `next` holds `modified_since` and `after_id`. "
    "Put both in their boxes and Execute again. `next` is null when you've got everything. "
    "Your extract script does exactly this in a loop."
)


@router.get(
    "/sales-orders", dependencies=[Depends(require_key)],
    summary="Sales orders, with their lines",
    description="One row per order, with every item on it inside `lines`. Orders marked SIMULATED come from the live simulator." + PAGING_HINT,
)
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


@router.get(
    "/sales-orders/{order_id}", dependencies=[Depends(require_key)],
    summary="One sales order by its id",
    description="Try order_id 43659: one order, many lines. 404 means there is no order with that id.",
)
def sales_order(order_id: int):
    h = db.one(f"select * from ({SALES_ORDERS}) x where id = %s", (order_id,))
    if not h:
        raise HTTPException(404, "No such order")
    o = clean(h)
    o["lines"] = [clean(r) for r in db.rows(f"select * from ({ORDER_LINES}) x where sales_order_id = %s order by id", (order_id,))]
    return o


@router.get(
    "/customers", dependencies=[Depends(require_key)],
    summary="Customers",
    description="One row per customer. Start here: it is the simplest table." + PAGING_HINT,
)
def customers(request: Request, modified_since: str | None = Since, after_id: int | None = After, limit: int = Limit):
    return page(request, CUSTOMERS, modified_since, after_id, limit)[0]


@router.get(
    "/products", dependencies=[Depends(require_key)],
    summary="Products",
    description="One row per product, with its price and category." + PAGING_HINT,
)
def products(request: Request, modified_since: str | None = Since, after_id: int | None = After, limit: int = Limit):
    return page(request, PRODUCTS, modified_since, after_id, limit)[0]


@router.get(
    "/inventory", dependencies=[Depends(require_key)],
    summary="Stock per product per location",
    description="One row per product at each location. id is product_id * 1000 + location_id." + PAGING_HINT,
)
def inventory(request: Request, modified_since: str | None = Since, after_id: int | None = After, limit: int = Limit):
    return page(request, INVENTORY, modified_since, after_id, limit)[0]
