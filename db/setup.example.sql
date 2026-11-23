-- What db/setup.sql looks like. Don't run this copy: run `python db/prepare_login.py`,
-- which writes db/setup.sql with a fresh random password (and the same password into .env).
-- Both of those files are in .gitignore, so the password never goes to GitHub.
CREATE ROLE aw_erp LOGIN PASSWORD 'made-by-prepare_login.py';
CREATE DATABASE adventureworks_erp OWNER aw_erp;
COMMENT ON DATABASE adventureworks_erp IS 'Microsoft AdventureWorks public sample data (fictional company). Portfolio practice, not client data.';
