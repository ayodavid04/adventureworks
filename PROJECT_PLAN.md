# AdventureWorks warehouse (practice project): the plan

## What this is

There's a pretend company system (an ERP) running on your laptop at http://localhost:4690. It has orders, customers and products. I built that part. It plays the company's system you've been given access to at work.

Your job: copy its data into your own database, clean it up, build reporting tables, and answer 5 business questions with it. You build all of that yourself.

## What to do next

AW 0.2: make the GitHub repo. Then AW 1.1: write the 5 business questions.

## Words used here

| Word | Means |
|---|---|
| ERP | the company's main system: orders, customers, products, stock |
| API | a web address your code calls to get data from the ERP, instead of clicking Download |
| Warehouse | your own database where you keep the copies and build the reporting tables |
| Raw | the first copy, exactly as it came from the ERP, never edited |
| dbt | a tool that runs your SQL to turn the raw copies into clean tables, and tests them |
| Webhook | the ERP messaging your app the moment something changes, instead of you asking |

## How to work through it

How to work through it: do the tasks in number order. Only have one task on the go at a time. Finish it, tick it, then start the next. The hours are a guess. Understanding each step matters more than speed.

The same list is in your planner (Career list, project board). Tick things off there.

## 0. Set up

Get access and somewhere to save your work.

- [x] **AW 0.1 Run the read-only login script**
  - Done already
- [ ] **AW 0.2 Make a GitHub repo for this project**
  - github.com, then New repository
  - Name it adventureworks-erp, leave it empty (no README)
  - Send Claude the link so it can push the code

## 1. Plan what you're building

Decide what the warehouse is for before you build it.

- [ ] **AW 1.1 Write 5 questions the business wants answered**
  - In Cursor, make a new file: docs/DESIGN.md
  - Write 5 questions a sales manager would ask, e.g. 'Which region sells the most each month?'
  - Under each one, one line on why they'd want to know
  - These decide what you build: if a table doesn't help answer one, skip it
- [ ] **AW 1.2 Draw how the data moves**
  - Boxes and arrows: ERP > your copy script > your warehouse > dbt > reporting tables > answers
  - Use draw.io (free, in the browser) or draw it on paper and take a photo
  - Save the picture in docs/ and link it in DESIGN.md
- [ ] **AW 1.3 Write down your choices and why**
  - Add a 'Decisions' heading to DESIGN.md
  - Your own database for the warehouse, apart from the ERP. Why: you never touch the company's system
  - Copy first, clean later. Why: you always keep the untouched copy
  - After the first copy, only fetch what changed. Why: faster, and it's how real jobs run

## 2. Get to know the ERP

You can't copy data you don't understand.

- [ ] **AW 2.1 Click around the ERP**
  - Open http://localhost:4690 and visit all 5 pages
  - On Integrations, download customers as CSV and as JSON
  - Open both files and see how they differ
- [ ] **AW 2.2 Look at the ERP's tables in DBeaver**
  - New connection: localhost, port 5432, database adventureworks_erp, user aw_readonly (details under Connect on the Integrations page)
  - Open sales.salesorderheader (orders) and sales.salesorderdetail (the items on each order)
  - Find the column that links them (salesorderid)
  - For each table write one line: 'one row = one order', 'one row = one item on an order'
- [ ] **AW 2.3 Try the API by hand**
  - Copy the API key from the Integrations page
  - In PowerShell, run the example call shown on that page
  - Look at 'next' at the bottom of the answer: that's how you ask for the next page
- [ ] **AW 2.4 Make a list of the tables you'll copy**
  - New file docs/source_dictionary.md
  - For each table: its name, 'one row = ...', its ID column, its 'last changed' column

## 3. Build your own warehouse

Your own database to copy into. You write this, not Claude.

- [ ] **AW 3.1 Write the SQL that creates your warehouse**
  - New file db/warehouse_setup.sql
  - CREATE ROLE aw_loader LOGIN PASSWORD '...'; then CREATE DATABASE aw_warehouse OWNER aw_loader;
  - Keep the real password in .env, put a placeholder in the file you commit
  - Run it in DBeaver on your postgres connection (Alt+X)
  - Connect to aw_warehouse as aw_loader and run CREATE SCHEMA raw;
- [ ] **AW 3.2 Make a table that remembers where you got to**
  - In aw_warehouse: raw._extract_state with columns endpoint, last_modified, last_id, last_run, rows_loaded
  - Each run reads it to know where it stopped last time, and updates it at the end

## 4. Copy the data in, one table at a time

Get one table fully working before starting the next.

- [ ] **AW 4.1 Customers, start to finish**
  - Make raw.customers: the columns the API gives you, plus _loaded_at and _batch_id
  - Write extract.py: call /api/v1/customers, keep asking for the next page until there isn't one, save every row
  - Check: rows in raw.customers = customers in the ERP
  - Save where you stopped in raw._extract_state
  - Run it again: it should copy 0 rows, because nothing changed
- [ ] **AW 4.2 Products and stock, the same way**
  - Same steps as customers, for /api/v1/products and /api/v1/inventory
- [ ] **AW 4.3 Orders and the items on them**
  - Each order comes with its items inside it
  - Orders go in raw.sales_orders, items in raw.order_lines
  - Check both counts against the ERP
- [ ] **AW 4.4 Test with live orders**
  - Start the simulator on the Integrations page, wait 5 minutes
  - Run extract.py
  - New orders copied should equal new orders the ERP made
- [ ] **AW 4.5 Add a quick data check after each run**
  - Print or save: rows copied, empty values in ID columns, duplicate IDs
  - If something looks wrong, stop and find out why before going on

## 5. Catch live updates (webhooks)

The ERP tells you about changes straight away, so you don't have to keep asking.

- [ ] **AW 5.1 Build a small app that receives the messages**
  - A small FastAPI app with one address the ERP can send to
  - Check the signature on each message (proves it really came from the ERP)
  - Save each message into raw.webhook_events
- [ ] **AW 5.2 Test what happens when things go wrong**
  - Wrong signature: must be refused
  - Same message twice: saved once
  - Stop your app, let the ERP retry, start it again: the message still arrives
- [ ] **AW 5.3 Connect it to the ERP**
  - Integrations page, Webhooks: add your app's address
  - Click Send test event
  - The delivery log should say 200 (that means it arrived)

## 6. Clean the data (dbt)

Turn the raw copies into tidy tables you can trust.

- [ ] **AW 6.1 Set up dbt and point it at your raw tables**
  - pip install dbt-postgres, then dbt init
  - Point it at aw_warehouse
  - List your raw tables in sources.yml
- [ ] **AW 6.2 Make one clean table per raw table**
  - Keep only the newest version of each row (the same order can be copied twice after it changes)
  - Tidy column names and types
- [ ] **AW 6.3 Add tests and descriptions**
  - Tests: IDs unique and never empty
  - A one-line description for each column
  - Run dbt docs generate: that's your data dictionary

## 7. Build the reporting tables

One big sales table with small tables around it, so questions are easy to answer.

- [ ] **AW 7.1 Build the sales table and the tables around it**
  - fact_sales: one row per item sold
  - Around it: dim_customer, dim_product, dim_date, dim_territory (region)
- [ ] **AW 7.2 Prove the totals match the ERP**
  - A dbt test: total sales in your tables = total sales in the ERP, to the penny
- [ ] **AW 7.3 Write up the double counting trap**
  - Shipping cost is on the order, not on each item
  - Join it to the items and it gets counted once per item
  - Show the wrong number, the right number, and how you fixed it

## 8. Keep history when customers move

When an address changes, keep the old one too, with dates.

- [ ] **AW 8.1 Track address changes over time**
  - A dbt snapshot on customer addresses
  - Let the simulator move a few people
  - Show one customer with the old and new address and the dates of each

## 9. Answer the 5 questions

The point of the whole thing.

- [ ] **AW 9.1 Answer your 5 questions**
  - One SQL query on your reporting tables for each question
  - One chart each
  - One sentence each saying what it shows

## 10. Write it up

So an employer gets it in 2 minutes.

- [ ] **AW 10.1 Write the README**
  - What it is in 3 lines, and the picture from 1.2
  - What's Microsoft's sample data, what's simulated, what you built
  - Test results and the totals check
  - Screenshots, and how to run it
- [ ] **AW 10.2 Push to GitHub and pin it**
  - Push
  - Pin the repo on your GitHub profile
