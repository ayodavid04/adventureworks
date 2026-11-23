"""The datasets the API and the Extract button serve. One query each, so both give the same rows.

Every dataset has an `id` and a `modified_at` column, which is what incremental extracts and
keyset paging run on. Times are UTC (the AdventureWorks dates have no time zone; read them as UTC).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

STATUS = {1: "In process", 2: "Approved", 3: "Backordered", 4: "Rejected", 5: "Shipped", 6: "Cancelled"}
STATUS_SQL = ("case h.status when 1 then 'In process' when 2 then 'Approved' when 3 then 'Backordered' "
              "when 4 then 'Rejected' when 5 then 'Shipped' when 6 then 'Cancelled' end")

SALES_ORDERS = f"""
select h.salesorderid as id, 'SO' || h.salesorderid as sales_order_number, h.revisionnumber as revision_number,
       h.orderdate as order_date, h.duedate as due_date, h.shipdate as ship_date,
       h.status as status_code, {STATUS_SQL} as status, h.onlineorderflag as online_order,
       h.customerid as customer_id, h.salespersonid as sales_person_id, h.territoryid as territory_id,
       t.name as territory, h.billtoaddressid as bill_to_address_id, h.shiptoaddressid as ship_to_address_id,
       h.shipmethodid as ship_method_id, h.purchaseordernumber as purchase_order_number,
       h.subtotal, h.taxamt as tax_amount, h.freight, h.totaldue as total_due, h.comment,
       h.modifieddate as modified_at
from sales.salesorderheader h
left join sales.salesterritory t on t.territoryid = h.territoryid
"""

ORDER_LINES = """
select d.salesorderdetailid as id, d.salesorderid as sales_order_id, h.orderdate as order_date,
       d.productid as product_id, p.productnumber as product_number, p.name as product_name,
       d.orderqty as order_qty, d.unitprice as unit_price, d.unitpricediscount as unit_price_discount,
       round(d.unitprice * (1 - d.unitpricediscount) * d.orderqty, 4) as line_total,
       d.specialofferid as special_offer_id, d.carriertrackingnumber as carrier_tracking_number,
       d.modifieddate as modified_at
from sales.salesorderdetail d
join sales.salesorderheader h on h.salesorderid = d.salesorderid
join production.product p on p.productid = d.productid
"""

CUSTOMERS = """
select c.customerid as id,
       'AW' || lpad(c.customerid::text, 8, '0') as account_number,
       case when c.storeid is not null then 'Store' else 'Individual' end as customer_type,
       coalesce(s.name, p.firstname || ' ' || p.lastname) as name,
       c.personid as person_id, c.storeid as store_id, c.territoryid as territory_id, t.name as territory,
       e.emailaddress as email,
       a.addressid as address_id, a.addressline1 as address_line1, a.addressline2 as address_line2,
       a.city, sp.name as state_province, a.postalcode as postal_code, sp.countryregioncode as country_code,
       c.modifieddate as modified_at
from sales.customer c
left join sales.store s on s.businessentityid = c.storeid
left join person.person p on p.businessentityid = c.personid
left join sales.salesterritory t on t.territoryid = c.territoryid
left join lateral (select emailaddress from person.emailaddress em
                   where em.businessentityid = c.personid order by emailaddressid limit 1) e on true
left join lateral (select bea.addressid from person.businessentityaddress bea
                   where bea.businessentityid = coalesce(c.storeid, c.personid)
                   order by (bea.addresstypeid in (2, 3)) desc, bea.addressid limit 1) ba on true
left join person.address a on a.addressid = ba.addressid
left join person.stateprovince sp on sp.stateprovinceid = a.stateprovinceid
"""

PRODUCTS = """
select p.productid as id, p.productnumber as product_number, p.name, pc.name as category,
       ps.name as subcategory, p.color, p.size, p.productline as product_line,
       p.finishedgoodsflag as finished_good, p.standardcost as standard_cost, p.listprice as list_price,
       p.sellstartdate as sell_start_date, p.sellenddate as sell_end_date,
       coalesce(inv.qty, 0) as quantity_on_hand, p.modifieddate as modified_at
from production.product p
left join production.productsubcategory ps on ps.productsubcategoryid = p.productsubcategoryid
left join production.productcategory pc on pc.productcategoryid = ps.productcategoryid
left join (select productid, sum(quantity) as qty from production.productinventory group by productid) inv
       on inv.productid = p.productid
"""

INVENTORY = """
select i.productid * 1000 + i.locationid as id, i.productid as product_id, p.productnumber as product_number,
       p.name as product_name, i.locationid as location_id, l.name as location, i.shelf, i.bin,
       i.quantity, i.modifieddate as modified_at
from production.productinventory i
join production.product p on p.productid = i.productid
join production.location l on l.locationid = i.locationid
"""

DATASETS = {
    "sales_orders": {"label": "Sales orders (headers)", "sql": SALES_ORDERS, "date_col": "order_date"},
    "order_lines": {"label": "Order lines", "sql": ORDER_LINES, "date_col": "order_date"},
    "customers": {"label": "Customers", "sql": CUSTOMERS, "date_col": "modified_at"},
    "products": {"label": "Products", "sql": PRODUCTS, "date_col": "modified_at"},
    "inventory": {"label": "Inventory (per product and location)", "sql": INVENTORY, "date_col": "modified_at"},
}


def parse_ts(value: str | None) -> datetime | None:
    """ISO 8601 in, naive UTC out (how the database stores it). '2025-06-01' and '...Z' both work."""
    if not value:
        return None
    v = value.strip()
    if "T" in v:
        v = v.replace(" ", "+")  # an unencoded '+00:00' in a URL arrives as ' 00:00'
    dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def to_json(value):
    if isinstance(value, datetime):
        # Full microseconds: a cursor rounded to milliseconds would hand the same row back again.
        return value.isoformat(timespec="microseconds") + "Z"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(round(value, 4))
    return value


def clean(row: dict) -> dict:
    return {k: to_json(v) for k, v in row.items()}


def extract_query(dataset: str, date_from: str | None, date_to: str | None, changed_since: str | None):
    """The Extract screen's query. Returns (sql, params) for the whole result, oldest first."""
    d = DATASETS[dataset]
    where, params = [], {}
    if date_from:
        where.append(f"{d['date_col']} >= %(date_from)s")
        params["date_from"] = parse_ts(date_from)
    if date_to:
        where.append(f"{d['date_col']} < (%(date_to)s::date + 1)")
        params["date_to"] = parse_ts(date_to)
    if changed_since:
        where.append("modified_at >= %(changed_since)s")
        params["changed_since"] = parse_ts(changed_since)
    sql = f"select * from ({d['sql']}) x" + (" where " + " and ".join(where) if where else "") + " order by id"
    return sql, params
