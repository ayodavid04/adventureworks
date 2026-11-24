# Build log

What I did, in order, with the command, the result and anything that went wrong. Screenshots for
each step are in [screenshots/build/](screenshots/build/), numbered in the order I took them.
The plan this follows is [PROJECT_PLAN.md](../PROJECT_PLAN.md).

> AdventureWorks is Microsoft's public sample data (a made-up bike company), not client data.

**Who built what:** the load scripts and the demo ERP front end were written with Claude (an AI
assistant). I ran every step that needed the postgres superuser myself. Everything from Part 1 on
(the design, my own warehouse database, the extractor, the webhook receiver, dbt, the analysis) is my own code.

---

## If someone asks "how did you make the database?"

I downloaded Microsoft's official AdventureWorks CSV files and a community Postgres port of its
install script, checked both against saved SHA-256 checksums, and cleaned the CSVs (separators,
byte order marks, binary columns) so Postgres could read them. I created a dedicated login and
database as the superuser, then ran the install script as that login. It built 68 tables across
5 schemas (sales, production, person, purchasing, humanresources) and loaded 31,465 sales orders
with 121,317 order lines. Then I put a small ERP app on top with a REST API, webhooks and a
simulator that creates new orders, so it behaves like a live system I can extract from.

---

## 2026-11-23: Load the AdventureWorks ERP database (Part 0)

**Why:** real work data often comes out of ERPs and CRMs: lots of related tables, order headers and
lines, keys everywhere. I wanted that shape to practise extraction and modelling on.

**Where the data came from:**

| What | Source | Licence | Pinned |
|---|---|---|---|
| The data (CSV files) | [microsoft/sql-server-samples](https://github.com/microsoft/sql-server-samples), AdventureWorks OLTP release | MIT | SHA-256 checksum in `scripts/fetch_source.py` |
| The Postgres install script | [lorint/AdventureWorks-for-Postgres](https://github.com/lorint/AdventureWorks-for-Postgres) `install.sql` | MIT | commit `b474991f` and its SHA-256 |

AdventureWorks is written for SQL Server, so it needs a port to run on Postgres.

**Steps:**

1. `python db/prepare_login.py`: makes a random password, puts it in `.env` (gitignored) and writes
   `db/setup.sql` (also gitignored).
2. I ran `db/setup.sql` as postgres. It creates the login `aw_erp` and the database
   `adventureworks_erp` owned by it. That's the only step that needs the superuser.
3. `python scripts/fetch_source.py`: downloads both sources, refuses them if the checksum doesn't
   match, then converts the CSVs (`scripts/convert_csvs.py`, a Python version of the port's Ruby
   script, so Ruby isn't needed).
4. `python scripts/load_source.py`: runs `install.sql` with psql as `aw_erp`, stopping on the
   first error. The output goes to `logs/load_source.log`.

**Result:** 68 tables and 19 views, no errors. 31,465 sales orders, 121,317 order lines,
19,820 customers, 504 products. Order dates run from 30 May 2022 to 29 Jun 2025.

**What went wrong / what I learned:**

- The port drops SQL Server's computed `LineTotal` column, so a line total has to be worked out:
  `unitprice * (1 - unitpricediscount) * orderqty`.
- The CSV load left the ID sequences at 1, so the first new order would have clashed with order 1.
  The app moves them past the existing IDs when it starts.
- Microsoft moved the sample's dates forward in newer releases, so they don't match older tutorials.
- DBeaver said "Invalid JDBC URL" because it was holding an old URL. A brand new connection in
  URL mode fixed it.

Screenshot: _(add)_

---

## 2026-11-23: Demo ERP front end (Part 0)

A small app over the database so it acts like a live system: 5 screens, a REST API, webhooks and a
live simulator. How it works is in the [README](../README.md#the-demo-erp-front-end) and the
screens are in [screenshots/](screenshots/). Simulated orders have `comment = 'SIMULATED'`, and every
change it makes is listed in `erp_app.simulator_log`.

---

## 2026-11-24: Read-only login (Part 0)

**Why:** an extractor should never be able to change the system it reads from.

1. `python db/prepare_readonly.py`: adds the `aw_readonly` password to `.env` and writes
   `db/readonly_login.sql` (gitignored).
2. I ran it as postgres. Result: `CREATE ROLE`.
3. Restarted the app, which grants that login SELECT on the five AdventureWorks schemas
   (nothing in `erp_app`, where the API key and webhook secrets are).
4. **Integrations > Connect > Test connection:** "Connected as aw_readonly ... Read-only confirmed
   (a test write was refused)."

Screenshot: _(add: Test connection result, with the API key hidden)_

---

## Next entry template

One entry per task from the planner (AW 1.1, AW 1.2 ...). Copy this to the bottom and fill it in.
To add a screenshot: take it with Win+Shift+S, click where it goes in this file in Cursor, press
Ctrl+V. Cursor saves the picture in `docs/screenshots/build/` and puts the link in for you.
Then rename the file to start with the task number, e.g. `AW-1.1-questions.png`.

```
## YYYY-MM-DD: AW x.y <task name> (Part N)

**Why:**

**Steps:**
1.

**Result:**

**What went wrong / what I learned:**

Screenshot: screenshots/build/AW-x.y-<name>.png
```

**Screenshot rule:** never capture a password or the API key (`.env`, a psql line with a password,
the Integrations page with the key shown).
