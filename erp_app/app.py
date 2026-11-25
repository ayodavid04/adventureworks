"""AdventureWorks ERP (demo): a thin ERP front end and integration layer over Microsoft's sample database."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import api, db, simulator, web


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.setup()
    yield
    simulator.stop()


app = FastAPI(
    title="AdventureWorks ERP (demo) API",
    description=(
        "Read API over Microsoft's AdventureWorks sample data (a fictional company). "
        "Orders with comment = 'SIMULATED' were made by the demo's live simulator.\n\n"
        "### How to use this page\n"
        "1. Open the ERP's **Integrations** page (http://localhost:4690/integrations) and copy the API key.\n"
        "2. Click **Authorize** (top right, the padlock), paste the key into X-API-Key, Authorize, Close. "
        "The padlocks shut: every call now sends the key.\n"
        "3. Open **GET /api/v1/customers**, click **Try it out**, set limit to 5, click **Execute**.\n"
        "4. Read the answer: **200** worked, **401** the key is missing or wrong, **400** a box has a bad value.\n"
        "5. **Page 2:** copy `modified_since` and `after_id` from `next` into their boxes and Execute again.\n"
        "6. The **Curl** box shows the same call as a command. Postman or PowerShell send exactly that."
    ),
    version="1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
app.include_router(api.router)
app.include_router(web.router)
