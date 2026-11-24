# Project plan: AdventureWorks ERP warehouse

How it's run: agile, as a kanban board. The design is settled first (part 1), then the build goes in small slices: one entity end to end (pull, land, check, re-run), then the next, so problems show up early. One card in Doing at a time. Every part ends with a 'done means' check, and that check includes the evidence (doc, test result, screenshot). The hours are a first guess, not a promise: aim to be able to explain every piece, not to finish fast.

The same list is on the planner's project board (Career list). Tick it off there; this copy lives with the code.

## Milestone 1: Understand the source

### 0. Set up

Done means: the read-only login works in DBeaver and the repo is on GitHub.

- [x] Run db/readonly_login.sql as postgres (10 min)
- [ ] Make the adventureworks-erp GitHub repo, send Claude the link (10 min)

### 1. Design

Done means: docs/DESIGN.md has the questions, a diagram and a decisions log.

- [ ] Write the 5 business questions the warehouse must answer (30 min)
- [ ] Draw the architecture: ERP > API + webhooks > aw_warehouse raw > dbt > marts (30 min)
- [ ] Start the decisions log (why a separate warehouse DB, why ELT, watermark + after_id, keys) (30 min)

### 2. Explore the ERP

Done means: docs/source_dictionary.md lists every table you'll pull, its grain and its keys.

- [ ] Click through the 5 ERP screens, download one CSV and one JSON (30 min)
- [ ] DBeaver as aw_readonly: map the sales tables (45 min)
- [ ] Call the API by hand with the key, note paging and modified_since (20 min)
- [ ] Write docs/source_dictionary.md (45 min)

## Milestone 2: Data in

### 3. Build your warehouse

Done means: aw_warehouse exists, your loader login can write raw, nothing can write to the ERP.

- [ ] Write db/warehouse_setup.sql yourself: database aw_warehouse, login aw_loader, schema raw (45 min)
- [ ] Create raw._extract_state (endpoint, watermark, last_id, last_run, rows) (20 min)

### 4. Extract in slices

Done means: for each slice the raw count matches the ERP and a re-run pulls only the changes.

- [ ] Slice 1, customers end to end: raw table, extractor, count check, incremental re-run (120 min)
- [ ] Slice 2: products and inventory (60 min)
- [ ] Slice 3: orders with their lines (nested JSON into raw.sales_orders + raw.order_lines) (90 min)
- [ ] Simulator on for 5 min, re-run, counts still match the ERP (30 min)
- [ ] Data quality report per run: rows, nulls, duplicates (45 min)

### 5. Webhook receiver

Done means: a test event lands, a bad signature is refused, the same event twice lands once.

- [ ] FastAPI receiver: check the HMAC signature, land into raw.webhook_events (90 min)
- [ ] Failure cases: bad signature, duplicate event, receiver down and the ERP retries (60 min)
- [ ] Register it on the Integrations page, send a test event, read the delivery log (20 min)

## Milestone 3: Warehouse

### 6. dbt staging

Done means: dbt build passes and dbt docs is generated (your data dictionary).

- [ ] Set up dbt, sources.yml on the raw tables (45 min)
- [ ] Staging models: latest version of each row (row_number on modifieddate) (90 min)
- [ ] Tests and column descriptions, then dbt docs generate (60 min)

### 7. Star schema and reconciliation

Done means: fact_sales totals match the ERP to the penny, as a dbt test.

- [ ] fact_sales at order-line grain + dim_customer, dim_product, dim_date, dim_territory (120 min)
- [ ] Reconciliation test: fact totals vs ERP / API totals (45 min)
- [ ] Write up the double counting trap (header freight repeated on every line) (30 min)

### 8. Snapshot

Done means: a customer who moved shows both addresses with valid_from / valid_to.

- [ ] dbt snapshot on customer address, let the simulator move people, show the history (60 min)

## Milestone 4: Delivery

### 9. Analysis

Done means: the 5 design questions answered in SQL from the marts, one chart each.

- [ ] Answer the 5 business questions from the marts (120 min)

### 10. Write-up

Done means: a README a hiring manager reads in 2 minutes, pushed and pinned.

- [ ] README: diagram, what's sample / simulated / yours, test + reconciliation results, screenshots (90 min)
- [ ] Push to GitHub, pin the repo on your profile (10 min)
