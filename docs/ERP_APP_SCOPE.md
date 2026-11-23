# Scope: a small ERP front end over AdventureWorks

## Why

AdventureWorks is only a database. Real data work starts from a *system*: an ERP with screens people use, an API, export buttons, and data that keeps changing while you extract it. This adds a thin front end and an integration layer so the database behaves like a working ERP I can connect to, pull from and receive live data from. Then I build the data side myself: the extract, the landing, dbt and the analysis.

It's a **demo**. The company, people and orders are Microsoft's fictional AdventureWorks sample (MIT licence). New orders made by the simulator are clearly flagged as simulated. It doesn't copy the look or branding of any real ERP product.

## What it is

A small web app, **"AdventureWorks ERP (demo)"**, running locally on `http://localhost:4690`. It reads and writes the existing `adventureworks_erp` database.

```
 ┌──────────────── the "system" (this build) ────────────────┐        ┌──────── my side (I build) ────────┐
 │                                                            │        │                                   │
 │  screens ─┐                                                │  pull  │  my extractor / my API             │
 │           ├── adventureworks_erp (Postgres) ── REST API ───┼───────>│   - watermark on modifieddate      │
 │  live     │      sales, production, person...              │        │   - lands rows as-is in raw       │
 │  order ───┘                                                │  push  │  webhook receiver ─────────┐       │
 │  simulator ──────────────── webhooks (order events) ───────┼───────>│                            v       │
 │                                                            │        │  raw ─dbt─> staging ─> marts ─> Python / Power BI
 │  Integrations page: connect, extract, download, webhooks   │        │                                   │
 └────────────────────────────────────────────────────────────┘        └───────────────────────────────────┘
```

## Screens (5, kept small)

| Screen | What's on it |
|---|---|
| **Home** | Orders today and this month, a feed of the latest orders updating live, the simulator's status (running or stopped) |
| **Sales orders** | A table with filters (date, status, territory, online or store). Click an order for its header and lines, with line totals worked out (the Postgres port has no `LineTotal`) |
| **Customers** | A table plus a customer page listing their orders |
| **Products and stock** | Products by category, with list price and quantity on hand per location |
| **Integrations** | The page that matters, see below |

## The Integrations page (the buttons to connect to)

1. **Connect.** Shows the read-only database details (host, port, database, a read-only login) and the REST API base URL plus an API key, with show/hide and copy. A **Test connection** button.
2. **Extract and download.** Pick a dataset (sales orders, order lines, customers, products, inventory) and a date range or "changed since". Click **Extract** for a preview and row count, then **Download CSV** or **Download JSON**. Every export goes in an export log.
3. **REST API.** A list of the endpoints with an example call for each:
   - `GET /api/v1/sales-orders?modified_since=...&after_id=...&limit=500`: header with its lines nested
   - `GET /api/v1/customers`, `/products`, `/inventory`, all with the same `modified_since` and `after_id`
   - API key in an `X-API-Key` header, keyset paging (`after_id`), times in UTC
4. **Webhooks (live push).** Register a URL (my receiver) and pick events: `order.created`, `order.updated` (status change), `customer.updated`. Each event is a JSON POST with an HMAC signature header. Includes **Send test event** and a delivery log (time, event, HTTP status, retries).
5. **Live simulator.** **Start** / **Stop** and a rate (orders per minute). While it runs:
   - it creates new orders from real customers, products and list prices, with order date and `modifieddate` set to now, flagged `comment = 'SIMULATED'`
   - it moves some open orders forward (approved, then shipped with a ship date, or occasionally cancelled), which bumps `modifieddate`
   - occasionally it changes a customer's address, so there's a slowly changing dimension to catch with a dbt snapshot
   - each change fires the matching webhook

## How it's built

- Python **FastAPI**, server-rendered HTML (Jinja2) and a little plain JavaScript for the live feed. No front-end framework. Python, so it matches the rest of my stack.
- The app's own tables live in a new schema, `erp_app` (api_keys, webhooks, webhook_deliveries, export_log, simulator_state). The AdventureWorks schemas keep their structure: the app only inserts and updates rows in them.
- A read-only database login for "Connect", separate from the app's owner login `aw_erp`.
- Started with one command, plus an entry in `C:\dev\.claude\launch.json`.
- Plain, dense business-app look: tables, filters, a left nav. Not a glossy dashboard.

## Not in this build

- My extractor, my API and webhook receiver, the warehouse `raw` landing, dbt, analysis. **Those are mine to build.** That's the point of the project.
- Logins and user roles, editing records by hand (beyond the simulator), mobile layout, deploying it online.

## Done means

- `python -m erp_app` (or similar) starts it on 4690, and every screen loads with real data
- Start the simulator, and new orders show on Home and in `GET /api/v1/sales-orders?modified_since=<5 minutes ago>`
- Download CSV gives the same row count as the preview
- **Send test event** reaches a throwaway local echo URL, used only to prove delivery, not as my receiver
- A screenshot of each screen in `docs/screenshots/`, and a README section that says what's sample data, what's simulated and what's mine

## Questions to check (with ChatGPT or anyone)

1. Should the warehouse be a **separate database** (more realistic, but needs one more postgres step) or a `raw` schema inside `adventureworks_erp`?
2. Is pull (REST with a watermark) plus push (webhooks) the right pair to practise, or is change data capture (Postgres logical replication, Debezium) worth adding later?
3. Is `modifieddate` a safe watermark when many rows share one timestamp? (Plan: `>` the last watermark with `after_id` as the tiebreak.)
4. Does flagging simulated orders with `comment = 'SIMULATED'` make it clear enough that they aren't Microsoft's data?
5. What would a hiring manager expect to see on top: tests, a data dictionary, an architecture diagram?
