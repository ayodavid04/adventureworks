# AdventureWorks ERP: practice warehouse on an ERP-shaped database

> **This is Microsoft's public sample data, not client data.** AdventureWorks is a made-up bike
> company that Microsoft publishes for training. Every customer, order and employee in it is fictional.

Real work data often comes from CRMs and ERPs: many related tables, header and line tables, keys
everywhere. This project gives me that shape to practise on. This repo **loads the raw ERP into
PostgreSQL** and puts a **small demo ERP front end** on it, so it behaves like a live system I can
connect to, extract from and receive changes from. Everything on the data side (extractor, receiver,
raw landing, dbt, analysis) is mine to write.

## What's what

| | Where | Who made it |
|---|---|---|
| **Microsoft sample data** | the `sales`, `production`, `person`, `purchasing`, `humanresources` schemas as loaded | Microsoft (fictional company) |
| **Simulated data** | orders with `comment = 'SIMULATED'` (tagged SIM on screen), their status changes and stock moves, and new customer addresses. Every change is listed in `erp_app.simulator_log` | the demo's live simulator |
| **The demo ERP** | `erp_app/` (screens, API, webhooks, simulator) and its own `erp_app` schema | Claude, built for this project |
| **The data side** | my extractor, my webhook receiver, raw landing, dbt, analysis | me (still to build) |

## The demo ERP front end

```powershell
.venv\Scripts\python -m erp_app
```

Then open http://localhost:4690. (It's also `adventureworks-erp` in `C:\dev\.claude\launch.json`.)

| Screen | What's on it |
|---|---|
| Home | Orders today and this month, open orders, the simulator's state, a live feed of the latest order changes |
| Sales orders | Filter by date, status, territory and channel; click an order for header and lines (line totals worked out, since the port has no `LineTotal`) |
| Customers | Search and filter; a customer page with their orders and any simulated address changes |
| Products and stock | Products by category with list price and quantity on hand; a product page with stock per location and price history |
| Integrations | Connect, Extract and download, REST API, Webhooks, Live simulator |

Screenshots of each are in [docs/screenshots/](docs/screenshots/).

**Integrations, the buttons to connect to:**

- **Connect:** read-only database details (login `aw_readonly`) and the API key, with show and copy, plus **Test connection**.
- **Extract and download:** pick a dataset and a date range or "changed since", preview it, download CSV or JSON. The download runs the preview's query, so the counts match. Every export is logged.
- **REST API:** `GET /api/v1/sales-orders` (lines nested), `/customers`, `/products`, `/inventory`. Send `X-API-Key`. Times are UTC. `modified_since` + `after_id` keyset paging: rows come in `(modified_at, id)` order and each page hands back the next cursor, so rows that share a timestamp are never skipped or repeated. Full reference at `/api/docs`.
- **Webhooks:** register a URL for `order.created`, `order.updated` and `customer.updated`. Each event is a signed JSON POST (`X-ERP-Signature: sha256=HMAC(secret, timestamp + "." + body)`), retried after 2 and 8 seconds. `/dev/echo` is a throwaway receiver that only proves delivery.
- **Live simulator:** start and stop it, and set a rate. Each tick it creates an order for a real customer with real products at list price. It moves open simulated orders on (In process, Approved, Shipped, sometimes Cancelled), and shipping takes stock out of Finished Goods Storage. Now and then a customer moves house: a new address row, with their home link repointed, so past orders keep their old address. It never edits Microsoft's historical orders, and it starts stopped every time the app starts.

Two things the app does to the database, so nothing is a surprise:
- It creates the `erp_app` schema for its own tables. It doesn't change the structure of the AdventureWorks schemas.
- It moves three ID sequences past the loaded data (orders, order lines, addresses). The CSV load left them at 1, so the first new order would otherwise have clashed with order 1.

To put the data back to pure Microsoft sample data: `python scripts/load_source.py --reset`.

**Read-only login:** `python db/prepare_readonly.py` writes `db/readonly_login.sql` (in `.gitignore`). Run it once as postgres, then restart the app, which grants it SELECT on the five AdventureWorks schemas. It gets nothing in `erp_app`, where the API key and webhook secrets live.

`python scripts/check_api.py` checks the API while the app is running: the key is required, and paging returns every customer exactly once.

## What's in the database

`adventureworks_erp` on local PostgreSQL 17, owned by its own login `aw_erp`.

| Schema | Tables | What it holds |
|---|---|---|
| `sales` | 19 | orders (header + lines), customers, stores, territories, special offers, currency |
| `production` | 25 | products, categories, bills of materials, inventory, work orders |
| `person` | 13 | people, addresses, emails, phones, countries |
| `purchasing` | 5 | vendors, purchase orders |
| `humanresources` | 6 | employees, departments, pay history |

68 tables in total, plus 19 of Microsoft's views. Some headline sizes: 31,465 sales orders, 121,317 order
lines, 19,820 customers, 504 products. Order dates run from 30 May 2022 to 29 Jun 2025.

`pe`, `hr`, `pr`, `pu` and `sa` are short-name views over the same tables, added by the Postgres port.

### Raw quirks worth knowing

- `sales.salesorderdetail` has no `LineTotal` column. In SQL Server it's a computed column, and the Postgres port drops it.
- Every table has `modifieddate` and `rowguid`.
- Microsoft moved the sample's dates forward in its newer releases, so they won't match older AdventureWorks tutorials.

## How it was loaded

```
Microsoft CSVs ──> convert_csvs.py ──> install.sql (psql) ──> adventureworks_erp
(official GitHub    (fixes separators,    (lorint/AdventureWorks-
 release)            BOMs, binary hex)     for-Postgres, pinned commit)
```

1. `python db/prepare_login.py` writes a random password into `.env` and writes `db/setup.sql`. Both are in `.gitignore`.
2. `db/setup.sql`, run once as postgres, creates the login and the database. Nothing else needs the superuser.
3. `python scripts/fetch_source.py` downloads the CSVs and the Postgres port. It checks both against saved SHA-256 checksums and refuses a file that changed, then converts the CSVs.
4. `python scripts/load_source.py` runs `install.sql` as `aw_erp`. Add `--reset` to drop the AdventureWorks schemas and load them again. Schemas you create yourself are kept.

`scripts/convert_csvs.py` is a Python port of the port's `update_csvs.rb`, so Ruby isn't needed. It converts the same 15 files.

## Connect in DBeaver

**Database > New Database Connection > PostgreSQL**, then choose **URL** mode:

| URL | Username | Password |
|---|---|---|
| `jdbc:postgresql://localhost:5432/adventureworks_erp` | `aw_erp` | the `PGPASSWORD` line in `.env` |

If DBeaver says "Invalid JDBC URL", it's reading an old URL. Cancel and make a brand new connection.

## What I'm building on top (my code)

- [ ] An extractor that pulls from the REST API (or the read-only login) with a `modified_since` watermark
- [ ] A webhook receiver (my own API) that checks the signature and lands events as they arrive
- [ ] Land copies of the ERP tables into a separate warehouse schema (`raw`)
- [ ] Staging models, one per source table
- [ ] Star schema: `fact_sales` from SalesOrderHeader + SalesOrderDetail, `dim_customer`, `dim_product`, `dim_date`, `dim_territory`
- [ ] Tests that the fact totals reconcile to the source
- [ ] An incremental load using `ModifiedDate`
- [ ] A dbt snapshot showing a slowly changing dimension
- [ ] A write-up of the order-lines double-counting trap and how the tests catch it
- [ ] A SQL workbook of practice queries

## Sources and licences

- AdventureWorks OLTP sample data: [microsoft/sql-server-samples](https://github.com/microsoft/sql-server-samples) (MIT licence).
- Postgres port: [lorint/AdventureWorks-for-Postgres](https://github.com/lorint/AdventureWorks-for-Postgres) (MIT licence), pinned in `scripts/fetch_source.py`.
- Downloaded files live in `data/download/` and are never committed.
