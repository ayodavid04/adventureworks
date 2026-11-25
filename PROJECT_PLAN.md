# AdventureWorks warehouse (practice project): the plan

## What this is

There's a pretend company system (an ERP) running on your laptop at http://localhost:4690. It has orders, customers and products. I built that part. It plays the company's system you've been given access to at work.

Your job: copy its data into your own database, clean it up, build reporting tables, and answer 5 business questions with it. You build all of that yourself.

## What to do next

AW 1.1: write the 5 business questions.

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

After each task: git add, git commit -m "AW x.y what you did", git push. Hints sit under each task's steps.

## 0. Set up

Get access and somewhere to save your work.

- [x] **AW 0.1 Run the read-only login script**
  - Done already
- [x] **AW 0.2 Make a GitHub repo for this project**
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
  - Hint: Good questions start with Which, How much, or Is: 'Which product category brings in the most money?'
  - Hint: Pick from what the data really has: region (territory), month, product category, customer type (Store or Individual), online or sales rep, discounts
  - Hint: Ideas: top 10 customers by spend; online vs rep orders; which month is busiest; which category has the best margin (list price minus standard cost)
  - Hint: Stuck? Ask 'what would a sales manager check every Monday morning?'
- [ ] **AW 1.2 Draw how the data moves**
  - Boxes and arrows: ERP > your copy script > your warehouse > dbt > reporting tables > answers
  - Use draw.io (free, in the browser) or draw it on paper and take a photo
  - Save the picture in docs/ and link it in DESIGN.md
  - Hint: draw.io is app.diagrams.net. Rectangles for each box, drag arrows between them
  - Hint: File > Export as > PNG, save it as docs/data-flow.png
  - Hint: Link it in DESIGN.md with: ![How the data moves](data-flow.png)
- [ ] **AW 1.3 Write down your choices and why**
  - Add a 'Decisions' heading to DESIGN.md
  - Your own database for the warehouse, apart from the ERP. Why: you never touch the company's system
  - Copy first, clean later. Why: you always keep the untouched copy
  - After the first copy, only fetch what changed. Why: faster, and it's how real jobs run
  - Hint: One or two lines per decision is enough. Employers read this to see you thought before you built

## 2. Get to know the ERP

You can't copy data you don't understand.

- [ ] **AW 2.1 Click around the ERP**
  - Open http://localhost:4690 and visit all 5 pages
  - On Integrations, download customers as CSV and as JSON
  - Open both files and see how they differ
  - Hint: CSV is flat (one row per line). JSON is nested (an order holds its items inside it). That's why APIs use JSON
  - Hint: Spot the modified_at column: it's what you'll use later to fetch only what changed
- [ ] **AW 2.2 Look at the ERP's tables in DBeaver**
  - New connection: localhost, port 5432, database adventureworks_erp, user aw_readonly (details under Connect on the Integrations page)
  - Open sales.salesorderheader (orders) and sales.salesorderdetail (the items on each order)
  - Find the column that links them (salesorderid)
  - For each table write one line: 'one row = one order', 'one row = one item on an order'
  - Hint: Easiest: New connection > PostgreSQL > URL mode, paste jdbc:postgresql://localhost:5432/adventureworks_erp
  - Hint: DBeaver only shows the database the connection names. That's why you only see Merseyside on your other one
  - Hint: Try: SELECT * FROM sales.salesorderdetail WHERE salesorderid = 43659; one order, many item rows
  - Hint: There's no LineTotal column. You work it out: unitprice * (1 - unitpricediscount) * orderqty
- [ ] **AW 2.3 Try the API by hand**
  - Copy the API key from the Integrations page
  - In PowerShell, run the example call shown on that page
  - Look at 'next' at the bottom of the answer: that's how you ask for the next page
  - Hint: Easiest place: http://localhost:4690/api/docs. Click GET /api/v1/customers, then Try it out
  - Hint: There's no Authorize button. After Try it out, an x-api-key box appears with the others: paste the key there
  - Hint: Set limit to 5, click Execute. 200 means it worked, 401 means the key is missing or wrong
  - Hint: Page 2: copy modified_since and after_id from 'next' into their boxes, Execute again. That's what your script will do in a loop
  - Hint: Then the same in Postman: GET the address, Headers tab, key X-API-Key, value your key, Send
- [ ] **AW 2.4 Make a list of the tables you'll copy**
  - New file docs/source_dictionary.md
  - For each table: its name, 'one row = ...', its ID column, its 'last changed' column
  - Hint: Use the column names the API gives you, not DBeaver's. The API renames them (customerid becomes id, modifieddate becomes modified_at)
  - Hint: Only 5 tables: customers, products, inventory, sales_orders, order_lines (the lines come inside each order)
  - Hint: Every one has id as its ID column and modified_at as its last changed column
  - Hint: Inventory's id is product_id * 1000 + location_id, so each product at each location gets one number

## 3. Build your own warehouse

Your own database to copy into. You write this, not Claude.

- [ ] **AW 3.1 Write the SQL that creates your warehouse**
  - New file db/warehouse_setup.sql
  - CREATE ROLE aw_loader LOGIN PASSWORD '...'; then CREATE DATABASE aw_warehouse OWNER aw_loader;
  - Keep the real password in .env, put a placeholder in the file you commit
  - Run it in DBeaver on your postgres connection (Alt+X)
  - Connect to aw_warehouse as aw_loader and run CREATE SCHEMA raw;
  - Hint: Open the SQL editor on the connection where you log in as postgres (the one showing Merseyside): right-click > SQL Editor > New script
  - Hint: Alt+X runs the whole script, Ctrl+Enter runs only the line your cursor is on
  - Hint: CREATE DATABASE won't run inside a transaction: check the toolbar says Auto (auto-commit)
  - Hint: In the file you commit write PASSWORD 'change-me'. The real one only goes in .env, which git ignores
  - Hint: Then a new DBeaver connection: database aw_warehouse, user aw_loader. Run CREATE SCHEMA raw; there
- [ ] **AW 3.2 Make a table that remembers where you got to**
  - In aw_warehouse: raw._extract_state with columns endpoint, last_modified, last_id, last_run, rows_loaded
  - Each run reads it to know where it stopped last time, and updates it at the end
  - Hint: Shape: CREATE TABLE raw._extract_state (endpoint text PRIMARY KEY, last_modified timestamptz, last_id bigint, last_run timestamptz, rows_loaded int);
  - Hint: One row per endpoint (customers, products ...)
  - Hint: To save it, use INSERT ... ON CONFLICT (endpoint) DO UPDATE SET ... so the same line works the first time and every time after

## 4. Copy the data in, one table at a time

Get one table fully working before starting the next.

- [ ] **AW 4.1 Customers, start to finish**
  - Make raw.customers: the columns the API gives you, plus _loaded_at and _batch_id
  - Write extract.py: call /api/v1/customers, keep asking for the next page until there isn't one, save every row
  - Check: rows in raw.customers = customers in the ERP
  - Save where you stopped in raw._extract_state
  - Run it again: it should copy 0 rows, because nothing changed
  - Hint: Install: pip install requests psycopg[binary] python-dotenv (inside .venv), and add them to requirements.txt
  - Hint: Start tiny: call with limit=5 and print the answer before you save anything
  - Hint: The loop: params = {'limit': 500}. Repeat: get the page, save page['data'], stop if page['next'] is empty, else params = {**page['next'], 'limit': 500}
  - Hint: Easy way to store rows: columns id, modified_at, payload jsonb (the whole row), _loaded_at, _batch_id. dbt unpacks payload later. Real teams do this
  - Hint: Second run: start from the saved last_modified and last_id. Pass both, or you'll copy the last row again
  - Hint: Save the state only after the rows are saved. If it crashes halfway, it redoes that page instead of skipping it
  - Hint: ERP count to match: 19,820 customers (SELECT count(*) FROM sales.customer on the ERP connection)
- [ ] **AW 4.2 Products and stock, the same way**
  - Same steps as customers, for /api/v1/products and /api/v1/inventory
  - Hint: Don't copy-paste the customers code. Turn it into one function, extract(endpoint, table), and call it three times
- [ ] **AW 4.3 Orders and the items on them**
  - Each order comes with its items inside it
  - Orders go in raw.sales_orders, items in raw.order_lines
  - Check both counts against the ERP
  - Hint: Each order has a 'lines' list. Take it out of the order (order.pop('lines')), save the order, then save each line
  - Hint: Expect 31,465 orders and 121,317 lines, plus whatever the simulator has made
- [ ] **AW 4.4 Test with live orders**
  - Start the simulator on the Integrations page, wait 5 minutes
  - Run extract.py
  - New orders copied should equal new orders the ERP made
  - Hint: Simulated orders have comment = 'SIMULATED'. Count them in the ERP and in your raw table
  - Hint: Orders that changed status come through again. That's right: raw keeps every version, dbt keeps the newest
- [ ] **AW 4.5 Add a quick data check after each run**
  - Print or save: rows copied, empty values in ID columns, duplicate IDs
  - If something looks wrong, stop and find out why before going on
  - Hint: Duplicate check: SELECT id, count(*) FROM raw.customers WHERE _batch_id = '<this run>' GROUP BY id HAVING count(*) > 1;
  - Hint: Across runs the same id twice is normal (it changed). Inside one run it's a bug

## 5. Catch live updates (webhooks)

The ERP tells you about changes straight away, so you don't have to keep asking.

- [ ] **AW 5.1 Build a small app that receives the messages**
  - A small FastAPI app with one address the ERP can send to
  - Check the signature on each message (proves it really came from the ERP)
  - Save each message into raw.webhook_events
  - Hint: Install: pip install fastapi uvicorn. Run it with: uvicorn receiver:app --port 8001
  - Hint: Headers it sends: X-ERP-Event, X-ERP-Delivery, X-ERP-Timestamp, X-ERP-Signature
  - Hint: Check the signature on the raw bytes: body = await request.body(). Don't rebuild the JSON first, the bytes must be exactly the same
  - Hint: Signature = 'sha256=' + HMAC-SHA256 of timestamp + '.' + body, using the secret. Compare with hmac.compare_digest
- [ ] **AW 5.2 Test what happens when things go wrong**
  - Wrong signature: must be refused
  - Same message twice: saved once
  - Stop your app, let the ERP retry, start it again: the message still arrives
  - Hint: Same message twice: X-ERP-Delivery is the same on retries. Make it UNIQUE and use ON CONFLICT DO NOTHING
  - Hint: Retries come after 2 and 8 seconds, so stop your app, send a test event, and start it again within about 8 seconds
- [ ] **AW 5.3 Connect it to the ERP**
  - Integrations page, Webhooks: add your app's address
  - Click Send test event
  - The delivery log should say 200 (that means it arrived)
  - Hint: Your address is http://localhost:8001/<your route>. Try /dev/echo first to see what a delivery looks like

## 6. Clean the data (dbt)

Turn the raw copies into tidy tables you can trust.

- [ ] **AW 6.1 Set up dbt and point it at your raw tables**
  - pip install dbt-postgres, then dbt init
  - Point it at aw_warehouse
  - List your raw tables in sources.yml
  - Hint: Inside .venv: pip install dbt-postgres. Then: dbt init aw_dbt
  - Hint: The login lives in C:/Users/<you>/.dbt/profiles.yml: host localhost, port 5432, user aw_loader, dbname aw_warehouse, schema analytics
  - Hint: dbt debug checks the connection works. Do that before anything else
  - Hint: sources.yml goes in models/staging/ and lists your 5 raw tables
- [ ] **AW 6.2 Make one clean table per raw table**
  - Keep only the newest version of each row (the same order can be copied twice after it changes)
  - Tidy column names and types
  - Hint: One file per table, e.g. models/staging/stg_customers.sql, reading from {{ source('raw', 'customers') }}
  - Hint: Newest version only: ROW_NUMBER() OVER (PARTITION BY id ORDER BY modified_at DESC, _loaded_at DESC) AS rn in a CTE, then WHERE rn = 1
  - Hint: That's the window function part of the SQL video. Watch it before this task
  - Hint: dbt run builds them. Check the result in DBeaver under the analytics schema
- [ ] **AW 6.3 Add tests and descriptions**
  - Tests: IDs unique and never empty
  - A one-line description for each column
  - Run dbt docs generate: that's your data dictionary
  - Hint: In a .yml next to the models: columns: - name: id, tests: [unique, not_null]
  - Hint: dbt test runs them. dbt docs generate then dbt docs serve opens your data dictionary in the browser

## 7. Build the reporting tables

One big sales table with small tables around it, so questions are easy to answer.

- [ ] **AW 7.1 Build the sales table and the tables around it**
  - fact_sales: one row per item sold
  - Around it: dim_customer, dim_product, dim_date, dim_territory (region)
  - Hint: Grain first: fact_sales is one row per order line. Join lines to their order for date, customer and territory
  - Hint: dim_date: one row per day, make it with generate_series in Postgres
  - Hint: Every dim has one row per thing (one per customer, one per product). Test the key is unique
- [ ] **AW 7.2 Prove the totals match the ERP**
  - A dbt test: total sales in your tables = total sales in the ERP, to the penny
  - Hint: A singular test: a .sql file in tests/ that returns rows when the totals differ. No rows back means pass
  - Hint: Compare sum of line_total in fact_sales with sum of subtotal on the orders
- [ ] **AW 7.3 Write up the double counting trap**
  - Shipping cost is on the order, not on each item
  - Join it to the items and it gets counted once per item
  - Show the wrong number, the right number, and how you fixed it
  - Hint: freight is on sales_orders. Join it to the lines and SUM(freight) is too big, once per item
  - Hint: Fix: total freight from the orders table, or split it across the lines by each line's share

## 8. Keep history when customers move

When an address changes, keep the old one too, with dates.

- [ ] **AW 8.1 Track address changes over time**
  - A dbt snapshot on customer addresses
  - Let the simulator move a few people
  - Show one customer with the old and new address and the dates of each
  - Hint: Snapshot with strategy timestamp, unique_key id, updated_at modified_at. The simulator updates modified_at when someone moves
  - Hint: Run dbt snapshot, let the simulator run, run dbt snapshot again
  - Hint: Look at dbt_valid_from and dbt_valid_to: the old address has an end date, the new one is open

## 9. Answer the 5 questions

The point of the whole thing.

- [ ] **AW 9.1 Answer your 5 questions**
  - One SQL query on your reporting tables for each question
  - One chart each
  - One sentence each saying what it shows
  - Hint: Charts: matplotlib in Python, Power BI, or even DBeaver's chart tab. Save each as a PNG in docs/answers/
  - Hint: The sentence says what it means for the business, not what the chart is: 'Bikes are 85% of sales, so ...'

## 10. Write it up

So an employer gets it in 2 minutes.

- [ ] **AW 10.1 Write the README**
  - What it is in 3 lines, and the picture from 1.2
  - What's Microsoft's sample data, what's simulated, what you built
  - Test results and the totals check
  - Screenshots, and how to run it
  - Hint: Write it for someone with 2 minutes: picture at the top, what you built, one headline result
- [ ] **AW 10.2 Push to GitHub and pin it**
  - Push
  - Pin the repo on your GitHub profile
  - Hint: GitHub profile > Customize your pins > tick adventureworks-erp
