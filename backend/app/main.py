"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload --port 8000   (from backend/)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import get_settings
from app.services.data_repository import DatasetError, get_repository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

settings = get_settings()
logging.getLogger(__name__).info(
    "CORS allowed origins: %s", settings.cors_origin_list)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Load datasets once at startup so the first request is fast."""
    try:
        get_repository()
    except DatasetError as exc:
        logging.getLogger(__name__).error("Dataset load failed: %s", exc)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Voyager AI - Agentic Travel Planner",
    description="LangChain tool-calling agent over flights/hotels/places "
                "datasets with live Open-Meteo weather.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def _validation_handler(_: Request, exc: RequestValidationError):
    messages = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
        msg = str(err.get("msg", "")).removeprefix("Value error, ")
        messages.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(status_code=422,
                        content={"detail": "; ".join(messages)})


@app.exception_handler(DatasetError)
async def _dataset_handler(_: Request, exc: DatasetError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/")
def root() -> dict:
    """Pointer to the API docs."""
    return {"service": "Voyager AI", "docs": "/docs", "health": "/api/health"}
