"""FastAPI entrypoint.  Run from /backend:  uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path

from . import db, store
from .config import get_settings
from .routes import guides, system

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.open_pool()
    seeded = await store.seed_if_empty(Path(__file__).resolve().parents[1] / "data" / "drafts")
    if seeded:
        logging.getLogger("db").info("local database was empty: loaded %d library guides", seeded)
    yield
    db.close_pool()


app = FastAPI(title="OAuth Guide API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(guides.router)
