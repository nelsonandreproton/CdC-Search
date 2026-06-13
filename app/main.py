"""Aplicação FastAPI — serve o diretório dinâmico."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routes import api, web

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.site_name, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(web.router)
app.include_router(api.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}
