"""Live simulator: makes the ERP behave like a system people are using right now.

While it runs, every tick (60 / orders-per-minute seconds) it:
  - creates a new order for a real customer, with real products at their list price,
    order date and modifieddate = now, and comment = 'SIMULATED' so it's never mistaken for Microsoft's data
  - often moves one or two open simulated orders on: In process -> Approved -> Shipped
    (ship date set, stock taken from Finished Goods Storage), now and then Cancelled
  - now and then moves a customer house (their home address changes), a slowly changing dimension
Each change bumps modifieddate, is logged in erp_app.simulator_log, and fires its webhook.
Only simulated orders are ever moved on. Microsoft's historical orders are never edited.
"""

from __future__ import annotations

import random
import threading
import time

from psycopg.types.json import Jsonb

from . import db, webhooks
from .datasets import CUSTOMERS, ORDER_LINES, SALES_ORDERS, STATUS, clean

FINISHED_GOODS = 7   # production.location 'Finished Goods Storage'
TAX_RATE, FREIGHT_RATE = 0.08, 0.025   # what AdventureWorks' own orders average
RESELLER_PRICE = 0.6                   # stores (resellers) pay about 60% of list in the sample

_thread: threading.Thread | None = None
_stop = threading.Event()
_lock = threading.Lock()
_cache: dict = {}
stats = {"orders_created": 0, "orders_updated": 0, "customers_updated": 0, "last_error": None}


def _load_cache() -> None:
    if _cache:
        return
    # each customer's latest order gives a real bill-to/ship-to address, card and sales person
    _cache["customers"] = db.rows("""
        select distinct on (h.customerid) h.customerid, h.billtoaddressid, h.shiptoaddressid, h.creditcardid,
               h.territoryid, h.salespersonid, h.onlineorderflag, h.shipmethodid, h.accountnumber,
               c.personid, c.storeid
        from sales.salesorderheader h join sales.customer c on c.customerid = h.customerid
        order by h.customerid, h.orderdate desc""")
    _cache["online"] = [c for c in _cache["customers"] if c["storeid"] is None]
    _cache["stores"] = [c for c in _cache["customers"] if c["storeid"] is not None]
    # products on sale now, that the 'No Discount' offer covers (the order line's foreign key needs it)
    _cache["products"] = db.rows("""
        select p.productid, p.listprice from production.product p
        where p.finishedgoodsflag and p.listprice > 0 and p.sellenddate is null
          and exists (select 1 from sales.specialofferproduct s where s.specialofferid = 1 and s.productid = p.productid)""")


def order_payload(order_id: int) -> dict:
    o = clean(db.one(f"select * from ({SALES_ORDERS}) x where id = %s", (order_id,)))
    o["lines"] = [clean(r) for r in db.rows(f"select * from ({ORDER_LINES}) x where sales_order_id = %s order by id", (order_id,))]
    return o


def create_order() -> int:
    is_store = random.random() < 0.12
    cust = random.choice(_cache["stores"] if is_store else _cache["online"])
    n_lines = random.randint(2, 8) if is_store else random.choice([1, 1, 1, 2, 2, 3])
    picks = random.sample(_cache["products"], n_lines)
    lines = []
    for p in picks:
        qty = random.randint(1, 6) if is_store else 1
        price = round(float(p["listprice"]) * (RESELLER_PRICE if is_store else 1.0), 4)
        lines.append((p["productid"], qty, price))
    subtotal = round(sum(q * pr for _, q, pr in lines), 4)
    tax, freight = round(subtotal * TAX_RATE, 4), round(subtotal * FREIGHT_RATE, 4)
    with db.conn() as c, c.transaction():
        oid = c.execute("""
            insert into sales.salesorderheader
              (revisionnumber, orderdate, duedate, status, onlineorderflag, purchaseordernumber, accountnumber,
               customerid, salespersonid, territoryid, billtoaddressid, shiptoaddressid, shipmethodid, creditcardid,
               subtotal, taxamt, freight, totaldue, comment, modifieddate)
            values (1, now(), now() + interval '12 days', 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, 'SIMULATED', now())
            returning salesorderid""",
            (not is_store, ("PO" + str(random.randint(10**9, 10**10))) if is_store else None, cust["accountnumber"],
             cust["customerid"], cust["salespersonid"] if is_store else None, cust["territoryid"],
             cust["billtoaddressid"], cust["shiptoaddressid"], 5 if is_store else 1, cust["creditcardid"],
             subtotal, tax, freight, round(subtotal + tax + freight, 4))).fetchone()["salesorderid"]
        for pid, qty, price in lines:
            c.execute("""insert into sales.salesorderdetail (salesorderid, orderqty, productid, specialofferid,
                         unitprice, unitpricediscount, modifieddate) values (%s, %s, %s, 1, %s, 0, now())""",
                      (oid, qty, pid, price))
        c.execute("insert into erp_app.simulator_log (change, entity_id, detail) values ('order.created', %s, %s)",
                  (oid, Jsonb({"lines": len(lines), "total_due": round(subtotal + tax + freight, 2)})))
    stats["orders_created"] += 1
    webhooks.emit("order.created", order_payload(oid))
    return oid


def advance_order() -> int | None:
    o = db.one("""select salesorderid, status from sales.salesorderheader
                  where comment = 'SIMULATED' and status in (1, 2) order by random() limit 1""")
    if not o:
        return None
    old = o["status"]
    new = 6 if random.random() < 0.05 else (2 if old == 1 else 5)
    with db.conn() as c, c.transaction():
        c.execute("""update sales.salesorderheader set status = %s, revisionnumber = revisionnumber + 1,
                     shipdate = case when %s = 5 then now() else shipdate end, modifieddate = now()
                     where salesorderid = %s""", (new, new, o["salesorderid"]))
        if new == 5:  # shipped: the stock leaves Finished Goods Storage
            c.execute("""update production.productinventory i set quantity = greatest(i.quantity - d.orderqty, 0),
                         modifieddate = now()
                         from sales.salesorderdetail d
                         where d.salesorderid = %s and i.productid = d.productid and i.locationid = %s""",
                      (o["salesorderid"], FINISHED_GOODS))
        c.execute("insert into erp_app.simulator_log (change, entity_id, detail) values ('order.updated', %s, %s)",
                  (o["salesorderid"], Jsonb({"from": STATUS[old], "to": STATUS[new]})))
    stats["orders_updated"] += 1
    payload = order_payload(o["salesorderid"])
    payload["previous_status"] = STATUS[old]
    webhooks.emit("order.updated", payload)
    return o["salesorderid"]


def move_customer() -> int | None:
    """An individual customer moves house. Like a real ERP, the new address is a new row and the
    customer's Home link points at it, so their past orders keep the address they shipped to."""
    cust = random.choice(_cache["online"])
    with db.conn() as c, c.transaction():
        home = c.execute("""select a.addressid, a.addressline1, a.city, a.postalcode, a.stateprovinceid
                            from person.businessentityaddress bea join person.address a using (addressid)
                            where bea.businessentityid = %s and bea.addresstypeid = 2 limit 1""",
                         (cust["personid"],)).fetchone()
        if not home:
            return None
        donor = c.execute("""select addressline1, city, postalcode from person.address
                             where stateprovinceid = %s and addressid <> %s order by random() limit 1""",
                          (home["stateprovinceid"], home["addressid"])).fetchone()
        if not donor:
            return None
        new_id = c.execute("""insert into person.address (addressline1, city, stateprovinceid, postalcode, modifieddate)
                              values (%s, %s, %s, %s, now()) returning addressid""",
                           (donor["addressline1"], donor["city"], home["stateprovinceid"], donor["postalcode"])
                           ).fetchone()["addressid"]
        c.execute("""update person.businessentityaddress set addressid = %s, modifieddate = now()
                     where businessentityid = %s and addresstypeid = 2 and addressid = %s""",
                  (new_id, cust["personid"], home["addressid"]))
        c.execute("update sales.customer set modifieddate = now() where customerid = %s", (cust["customerid"],))
        old = {k: home[k] for k in ("addressid", "addressline1", "city", "postalcode")}
        c.execute("insert into erp_app.simulator_log (change, entity_id, detail) values ('customer.updated', %s, %s)",
                  (cust["customerid"], Jsonb({"old": old, "new": {"addressid": new_id, **dict(donor)}})))
    stats["customers_updated"] += 1
    data = clean(db.one(f"select * from ({CUSTOMERS}) x where id = %s", (cust["customerid"],)))
    data["previous_address"] = old
    webhooks.emit("customer.updated", data)
    return cust["customerid"]


def tick() -> None:
    create_order()
    if random.random() < 0.7:
        for _ in range(random.choice([1, 1, 2])):
            advance_order()
    if random.random() < 0.12:
        move_customer()


def _run() -> None:
    _load_cache()
    while not _stop.is_set():
        try:
            tick()
            stats["last_error"] = None
        except Exception as e:  # keep going; show the error on the page
            stats["last_error"] = str(e)[:300]
        rate = db.one("select orders_per_min from erp_app.simulator_state")["orders_per_min"]
        _stop.wait(60 / max(rate, 1))


def running() -> bool:
    return _thread is not None and _thread.is_alive()


def start(rate: int) -> None:
    global _thread
    with _lock:
        db.one("""update erp_app.simulator_state set running = true, orders_per_min = %s, started_at = now()
                  returning 1""", (max(1, min(rate, 60)),))
        if not running():
            _stop.clear()
            _thread = threading.Thread(target=_run, daemon=True, name="simulator")
            _thread.start()


def stop() -> None:
    with _lock:
        _stop.set()
        db.one("update erp_app.simulator_state set running = false, stopped_at = now() returning 1")


def set_rate(rate: int) -> None:
    db.one("update erp_app.simulator_state set orders_per_min = %s returning 1", (max(1, min(rate, 60)),))
