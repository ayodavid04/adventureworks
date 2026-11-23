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
    description="Read API over Microsoft's AdventureWorks sample data (a fictional company). "
                "Orders with comment = 'SIMULATED' were made by the demo's live simulator.",
    version="1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
app.include_router(api.router)
app.include_router(web.router)
