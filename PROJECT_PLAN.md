# Project plan: AdventureWorks ERP warehouse

**How it's run:** Kanban (agile), not sprints: no team and no fixed deadline. The parts go in order because each one needs the one before (that bit looks like waterfall), but inside a part you work the board: one card in Doing at a time, finish it, pull the next. Each part ends with a 'done means' check, so you always know when to move on.

The same list is in the planner (Career list, project board), so tick it off there. This file is the copy that lives with the code.

## 0. Set up

Done means: Read-only login works in DBeaver, repo is on GitHub

- [ ] Run db/readonly_login.sql as postgres (DBeaver, Alt+X) (10 min)
- [ ] Make the adventureworks-erp GitHub repo, send Claude the link (10 min)

## 1. Explore the system

Done means: You can explain the 5 sales tables and how an order and its lines join

- [ ] Click through the 5 ERP screens, download one CSV and one JSON (30 min)
- [ ] Connect DBeaver as the read-only login, map the sales tables (45 min)
- [ ] Call /api/v1/sales-orders by hand (browser or curl) with the API key (20 min)

## 2. Raw landing

Done means: raw tables exist with audit columns and an empty watermark table

- [ ] Decide: separate warehouse database or raw schema (write why) (15 min)
- [ ] Create raw tables + audit columns (_batch_id, _loaded_at, _source) (60 min)
- [ ] Create raw._extract_state (endpoint, watermark, last run, rows) (20 min)

## 3. Extractor (pull)

Done means: Incremental run after 5 min of simulator picks up exactly the new and changed orders

- [ ] Full pull: Python calls the API, pages with after_id, lands as-is (90 min)
- [ ] Incremental pull on modified_since, watermark moves only after commit (90 min)
- [ ] Test: simulator on 5 min, incremental run, counts match the ERP (30 min)

## 4. Webhook receiver (push)

Done means: Live order events land in raw with the signature checked

- [ ] FastAPI receiver: check the HMAC signature, land into raw.webhook_events (90 min)
- [ ] Register it on the Integrations page, send a test event, read the log (20 min)

## 5. dbt staging

Done means: dbt build passes with tests on every staging model

- [ ] Set up dbt, sources.yml on the raw tables (45 min)
- [ ] Staging models: latest version of each row (row_number on modifieddate) (90 min)
- [ ] Tests: unique, not_null, relationships, accepted_values (45 min)

## 6. Star schema

Done means: fact_sales totals match the ERP to the penny

- [ ] fact_sales at order-line grain + dim_customer, dim_product, dim_date, dim_territory (120 min)
- [ ] Reconciliation test: fact totals vs ERP / API totals (45 min)
- [ ] Write up the order-lines double counting trap (header freight x lines) (30 min)

## 7. Snapshot (changing customers)

Done means: A customer who moved house shows both addresses with valid_from / valid_to

- [ ] dbt snapshot on customer address, let the simulator move people, show history (60 min)

## 8. Write-up

Done means: README a hiring manager can read in 2 minutes, pushed to GitHub

- [ ] README: diagram, what's sample / simulated / yours, screenshots, how to run (90 min)
- [ ] Push to GitHub, pin the repo on your profile (10 min)
