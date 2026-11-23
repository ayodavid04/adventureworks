# AdventureWorks ERP: practice warehouse on an ERP-shaped database

> **This is Microsoft's public sample data, not client data.** AdventureWorks is a made-up bike
> company that Microsoft publishes for training. Every customer, order and employee in it is fictional.

Real work data often comes from CRMs and ERPs: many related tables, header and line tables, keys
everywhere. This project gives me that shape to practise on. This repo only **loads the raw ERP
into PostgreSQL**. Everything built on top of it (staging, star schema, tests) is mine to write.

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
