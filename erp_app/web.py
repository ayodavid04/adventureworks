"""The screens: Home, Sales orders, Customers, Products and stock, Integrations."""

from __future__ import annotations

import csv
import io
import json
import os
import secrets
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from psycopg.types.json import Jsonb

from . import db, simulator, webhooks
from .datasets import (CUSTOMERS, DATASETS, ORDER_LINES, PRODUCTS, SALES_ORDERS, STATUS, clean,
                       extract_query, to_json)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
PAGE = 50
ECHO: deque = deque(maxlen=20)   # what the throwaway echo receiver got, newest first


def money(v) -> str:
    return "" if v is None else f"{float(v):,.2f}"


def when(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M") if (v.hour or v.minute or v.second) else v.strftime("%Y-%m-%d")
    return str(v)


templates.env.filters["money"] = money
templates.env.filters["when"] = when
templates.env.globals["STATUS"] = STATUS


def render(request: Request, name: str, **ctx):
    ctx.setdefault("nav", name.split(".")[0])
    return templates.TemplateResponse(request, name, ctx)


def paged(sql: str, params: dict, page: int, order: str):
    page = max(page, 1)
    data = db.rows(f"select *, count(*) over () as _total from ({sql}) x {order} limit {PAGE} offset {(page - 1) * PAGE}",
                   params)
    total = data[0]["_total"] if data else 0
    return data, {"page": page, "pages": max((total + PAGE - 1) // PAGE, 1), "total": total}


def territories():
    return db.rows("select territoryid as id, name, \"group\" from sales.salesterritory order by \"group\", name")


# ------------------------------------------------------------------ Home
def home_numbers() -> dict:
    n = db.one("""select count(*) filter (where orderdate >= date_trunc('day', now()))   as today_orders,
                         coalesce(sum(totaldue) filter (where orderdate >= date_trunc('day', now())), 0) as today_value,
                         count(*) filter (where orderdate >= date_trunc('month', now())) as month_orders,
                         coalesce(sum(totaldue) filter (where orderdate >= date_trunc('month', now())), 0) as month_value,
                         count(*) filter (where status in (1, 2, 3))                     as open_orders,
                         count(*) filter (where comment = 'SIMULATED')                   as simulated_orders,
                         max(orderdate)                                                  as last_order
                  from sales.salesorderheader""")
    state = db.one("select * from erp_app.simulator_state")
    return {**n, "sim": state, "sim_alive": simulator.running(), "stats": simulator.stats}


def latest_orders(limit: int = 15):
    return db.rows(f"select * from ({SALES_ORDERS}) x order by modified_at desc, id desc limit %s", (limit,))


@router.get("/")
def home(request: Request):
    return render(request, "home.html", n=home_numbers(), feed=latest_orders(), nav="home")


@router.get("/ui/feed")
def feed():
    n = home_numbers()
    return {"numbers": {k: to_json(v) for k, v in n.items() if k not in ("sim", "stats")},
            "sim_running": bool(n["sim"]["running"]) and n["sim_alive"], "stats": simulator.stats,
            "rate": n["sim"]["orders_per_min"],
            "orders": [{**clean(r), "total_due_fmt": money(r["total_due"]), "modified_fmt": when(r["modified_at"]),
                        "order_fmt": when(r["order_date"])} for r in latest_orders()]}


# ------------------------------------------------------------------ Sales orders
@router.get("/orders")
def orders(request: Request, date_from: str = "", date_to: str = "", status: str = "", territory: str = "",
           channel: str = "", q: str = "", page: int = 1):
    where, p = [], {}
    if date_from:
        where.append("order_date >= %(df)s"); p["df"] = date_from
    if date_to:
        where.append("order_date < %(dt)s::date + 1"); p["dt"] = date_to
    if status:
        where.append("status_code = %(st)s"); p["st"] = int(status)
    if territory:
        where.append("territory_id = %(te)s"); p["te"] = int(territory)
    if channel in ("online", "store"):
        where.append("online_order = %(on)s"); p["on"] = channel == "online"
    if q:
        where.append("(sales_order_number ilike %(q)s or purchase_order_number ilike %(q)s or id::text = %(qe)s)")
        p["q"], p["qe"] = f"%{q.strip()}%", q.strip().upper().removeprefix("SO")
    sql = f"""select x.*, coalesce(s.name, pp.firstname || ' ' || pp.lastname) as customer_name
              from ({SALES_ORDERS}) x join sales.customer c on c.customerid = x.customer_id
              left join sales.store s on s.businessentityid = c.storeid
              left join person.person pp on pp.businessentityid = c.personid""" + (
        " where " + " and ".join(where) if where else "")
    data, pg = paged(sql, p, page, "order by order_date desc, id desc")
    args = {k: v for k, v in dict(date_from=date_from, date_to=date_to, status=status, territory=territory,
                                   channel=channel, q=q).items() if v}
    return render(request, "orders.html", rows=data, pg=pg, args=args, territories=territories(), nav="orders")


@router.get("/orders/{order_id}")
def order(request: Request, order_id: int):
    h = db.one(f"""select x.*, coalesce(s.name, pp.firstname || ' ' || pp.lastname) as customer_name,
                         sm.name as ship_method,
                         concat_ws(', ', ba.addressline1, ba.city, ba.postalcode) as bill_to,
                         concat_ws(', ', sa.addressline1, sa.city, sa.postalcode) as ship_to,
                         sp_p.firstname || ' ' || sp_p.lastname as sales_person
                  from ({SALES_ORDERS}) x
                  join sales.customer c on c.customerid = x.customer_id
                  left join sales.store s on s.businessentityid = c.storeid
                  left join person.person pp on pp.businessentityid = c.personid
                  left join purchasing.shipmethod sm on sm.shipmethodid = x.ship_method_id
                  left join person.address ba on ba.addressid = x.bill_to_address_id
                  left join person.address sa on sa.addressid = x.ship_to_address_id
                  left join person.person sp_p on sp_p.businessentityid = x.sales_person_id
                  where x.id = %s""", (order_id,))
    if not h:
        raise HTTPException(404, "No such order")
    lines = db.rows(f"select * from ({ORDER_LINES}) x where sales_order_id = %s order by id", (order_id,))
    return render(request, "order.html", h=h, lines=lines, lines_total=sum(l["line_total"] for l in lines), nav="orders")


# ------------------------------------------------------------------ Customers
@router.get("/customers")
def customers(request: Request, q: str = "", type: str = "", territory: str = "", page: int = 1):
    where, p = [], {}
    if q:
        where.append("(name ilike %(q)s or account_number ilike %(q)s or email ilike %(q)s)"); p["q"] = f"%{q.strip()}%"
    if type in ("Individual", "Store"):
        where.append("customer_type = %(ty)s"); p["ty"] = type
    if territory:
        where.append("territory_id = %(te)s"); p["te"] = int(territory)
    sql = f"""select x.*, o.orders, o.last_order, o.lifetime_value from ({CUSTOMERS}) x
              left join (select customerid, count(*) as orders, max(orderdate) as last_order, sum(totaldue) as lifetime_value
                         from sales.salesorderheader group by customerid) o on o.customerid = x.id""" + (
        " where " + " and ".join(where) if where else "")
    data, pg = paged(sql, p, page, "order by id")
    args = {k: v for k, v in dict(q=q, type=type, territory=territory).items() if v}
    return render(request, "customers.html", rows=data, pg=pg, args=args, territories=territories(), nav="customers")


@router.get("/customers/{customer_id}")
def customer(request: Request, customer_id: int, page: int = 1):
    c = db.one(f"select * from ({CUSTOMERS}) x where id = %s", (customer_id,))
    if not c:
        raise HTTPException(404, "No such customer")
    data, pg = paged(f"select * from ({SALES_ORDERS}) x where customer_id = %(c)s", {"c": customer_id}, page,
                     "order by order_date desc, id desc")
    tot = db.one("select count(*) as n, sum(totaldue) as v from sales.salesorderheader where customerid = %s", (customer_id,))
    moves = db.rows("select created_at, detail from erp_app.simulator_log where change = 'customer.updated' "
                    "and entity_id = %s order by log_id desc", (customer_id,))
    return render(request, "customer.html", c=c, rows=data, pg=pg, tot=tot, moves=moves, args={}, nav="customers")


# ------------------------------------------------------------------ Products and stock
@router.get("/products")
def products(request: Request, category: str = "", q: str = "", stock: str = "", page: int = 1):
    where, p = [], {}
    if category:
        where.append("coalesce(category, 'Components / parts') = %(ca)s"); p["ca"] = category
    if q:
        where.append("(name ilike %(q)s or product_number ilike %(q)s)"); p["q"] = f"%{q.strip()}%"
    if stock == "low":
        where.append("quantity_on_hand < 100")
    sql = f"select * from ({PRODUCTS}) x" + (" where " + " and ".join(where) if where else "")
    data, pg = paged(sql, p, page, "order by category nulls last, subcategory, name")
    cats = db.rows(f"select coalesce(category, 'Components / parts') as category, count(*) as n, "
                   f"sum(quantity_on_hand) as qty from ({PRODUCTS}) x group by 1 order by 1")
    args = {k: v for k, v in dict(category=category, q=q, stock=stock).items() if v}
    return render(request, "products.html", rows=data, pg=pg, args=args, cats=cats, nav="products")


@router.get("/products/{product_id}")
def product(request: Request, product_id: int):
    p = db.one(f"select * from ({PRODUCTS}) x where id = %s", (product_id,))
    if not p:
        raise HTTPException(404, "No such product")
    stock = db.rows("""select l.name as location, i.shelf, i.bin, i.quantity, i.modifieddate
                       from production.productinventory i join production.location l using (locationid)
                       where i.productid = %s order by l.locationid""", (product_id,))
    sales = db.one("""select count(distinct salesorderid) as orders, sum(orderqty) as units,
                             sum(unitprice * (1 - unitpricediscount) * orderqty) as revenue
                      from sales.salesorderdetail where productid = %s""", (product_id,))
    prices = db.rows("select startdate, enddate, listprice from production.productlistpricehistory "
                     "where productid = %s order by startdate", (product_id,))
    return render(request, "product.html", p=p, stock=stock, sales=sales, prices=prices, nav="products")


# ------------------------------------------------------------------ Integrations
@router.get("/integrations")
def integrations(request: Request):
    e = os.environ
    with db.conn() as c:
        ro = db.readonly_exists(c)
    base = f"{request.url.scheme}://{request.url.netloc}"
    return render(
        request, "integrations.html", nav="integrations", base=base, api_key=db.api_key(),
        conn={"host": "localhost", "port": e.get("PGPORT", "5432"), "database": e["PGDATABASE"],
              "user": e.get("AW_READONLY_USER", db.READONLY_USER), "password": e.get("AW_READONLY_PASSWORD", ""),
              "exists": ro},
        datasets=DATASETS, exports=db.rows("select * from erp_app.export_log order by export_id desc limit 10"),
        hooks=db.rows("select * from erp_app.webhooks order by webhook_id"), events=webhooks.EVENTS,
        deliveries=deliveries_rows(), sim=db.one("select * from erp_app.simulator_state"),
        sim_alive=simulator.running(), stats=simulator.stats, echo=list(ECHO),
        sim_log=db.rows("select * from erp_app.simulator_log order by log_id desc limit 12"),
        five_min_ago=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )


@router.post("/integrations/test-connection")
def test_connection():
    e = os.environ
    user, pw = e.get("AW_READONLY_USER", db.READONLY_USER), e.get("AW_READONLY_PASSWORD", "")
    t0 = time.perf_counter()
    try:
        with psycopg.connect(db.conninfo(user, pw), connect_timeout=5) as c:
            v = c.execute("select version()").fetchone()[0].split(",")[0]
            n = c.execute("select count(*) from sales.salesorderheader").fetchone()[0]
            try:
                c.execute("create table sales._write_probe (x int)")
                writable = True
            except psycopg.Error:
                writable = False
            c.rollback()  # never keep the probe, whatever happened
        ms = round((time.perf_counter() - t0) * 1000)
        return {"ok": True, "message": f"Connected as {user} in {ms} ms. {v}. sales.salesorderheader has {n:,} rows. "
                + ("WARNING: this login can write." if writable else "Read-only confirmed (a test write was refused).")}
    except psycopg.OperationalError as ex:
        msg = str(ex).strip().splitlines()[-1]
        hint = (" The read-only login doesn't exist yet: run db/readonly_login.sql as postgres, then restart the app."
                if "password authentication failed" in msg or "does not exist" in msg else "")
        return {"ok": False, "message": f"Could not connect as {user}: {msg}.{hint}"}


@router.post("/integrations/extract")
def extract(dataset: str = Form(...), date_from: str = Form(""), date_to: str = Form(""), changed_since: str = Form("")):
    if dataset not in DATASETS:
        raise HTTPException(400, "Unknown dataset")
    try:
        sql, p = extract_query(dataset, date_from, date_to, changed_since)
    except ValueError:
        return JSONResponse({"error": "Dates must look like 2025-06-01 or 2025-06-01T09:00:00Z"}, 400)
    n = db.one(f"select count(*) as n from ({sql}) y", p)["n"]
    preview = db.rows(sql + " limit 25", p)
    cols = list(preview[0].keys()) if preview else []
    return {"count": n, "columns": cols, "rows": [[to_json(r[c]) for c in cols] for r in preview]}


@router.get("/integrations/download")
def download(dataset: str, format: str = "csv", date_from: str = "", date_to: str = "", changed_since: str = ""):
    if dataset not in DATASETS or format not in ("csv", "json"):
        raise HTTPException(400, "Unknown dataset or format")
    sql, p = extract_query(dataset, date_from, date_to, changed_since)
    with db.conn() as c:
        cur = c.execute(sql, p)
        data = cur.fetchall()
        columns = [col.name for col in cur.description]   # so an empty extract still has a header row
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filters = {k: v for k, v in dict(date_from=date_from, date_to=date_to, changed_since=changed_since).items() if v}
    db.one("insert into erp_app.export_log (dataset, filters, file_format, row_count) values (%s, %s, %s, %s) returning 1",
           (dataset, Jsonb(filters), format, len(data)))
    name = f"adventureworks_{dataset}_{stamp}.{format}"
    if format == "json":
        body = json.dumps([clean(r) for r in data], ensure_ascii=False)
        media = "application/json"
    else:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(columns)
        for r in data:
            w.writerow(["" if v is None else to_json(v) for v in r.values()])
        body, media = buf.getvalue(), "text/csv"
    return Response(body.encode("utf-8"), media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "X-Row-Count": str(len(data))})


@router.post("/integrations/webhooks")
def add_webhook(url: str = Form(...), events: list[str] = Form(default=[])):
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "The URL must start with http:// or https://")
    events = [e for e in events if e in webhooks.EVENTS] or list(webhooks.EVENTS)
    db.one("insert into erp_app.webhooks (url, events, secret) values (%s, %s, %s) returning 1",
           (url, events, "whsec_" + secrets.token_urlsafe(24)))
    return RedirectResponse("/integrations#webhooks", status_code=303)


@router.post("/integrations/webhooks/{webhook_id}/test")
def test_webhook(webhook_id: int):
    webhooks.send_test(webhook_id)
    return RedirectResponse("/integrations#webhooks", status_code=303)


@router.post("/integrations/webhooks/{webhook_id}/toggle")
def toggle_webhook(webhook_id: int):
    db.one("update erp_app.webhooks set active = not active where webhook_id = %s returning 1", (webhook_id,))
    return RedirectResponse("/integrations#webhooks", status_code=303)


@router.post("/integrations/webhooks/{webhook_id}/delete")
def delete_webhook(webhook_id: int):
    db.one("delete from erp_app.webhooks where webhook_id = %s returning 1", (webhook_id,))
    return RedirectResponse("/integrations#webhooks", status_code=303)


def deliveries_rows():
    return db.rows("""select d.created_at, d.event, w.url, d.status, d.http_status, d.attempts, d.last_error
                      from erp_app.webhook_deliveries d join erp_app.webhooks w using (webhook_id)
                      order by d.created_at desc limit 15""")


@router.get("/ui/deliveries")
def deliveries():
    return [{**{k: to_json(v) for k, v in r.items()}, "created_fmt": r["created_at"].strftime("%H:%M:%S")}
            for r in deliveries_rows()]


@router.post("/integrations/simulator/start")
def sim_start(rate: int = Form(6)):
    simulator.start(rate)
    return RedirectResponse("/integrations#simulator", status_code=303)


@router.post("/integrations/simulator/stop")
def sim_stop():
    simulator.stop()
    return RedirectResponse("/integrations#simulator", status_code=303)


# A throwaway receiver, only to prove a webhook leaves and arrives. NOT the real receiver:
# that's built on the data side, outside this app.
@router.post("/dev/echo")
async def echo(request: Request):
    body = await request.body()
    ECHO.appendleft({"at": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                     "event": request.headers.get("x-erp-event"), "bytes": len(body),
                     "signature": (request.headers.get("x-erp-signature") or "")[:23] + "..."})
    return {"received": True}
