"""Painel de administração protegido: histórico e disparo manual da recolha.

Protegido por ``ADMIN_TOKEN`` (header ``X-Admin-Token`` ou query/form ``token``).
Se ``ADMIN_TOKEN`` estiver vazio, o admin está desativado (403).
"""
from __future__ import annotations

import datetime as dt
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.models import IngestRun
from app.routes.web import _ctx, templates

router = APIRouter(prefix="/admin")

# Janela após a qual uma execução "running" é considerada presa (e ignorada).
STALE_RUN_AFTER = dt.timedelta(hours=2)


def _check_token(token: str | None) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="Admin desativado: define ADMIN_TOKEN.")
    if not token or not secrets.compare_digest(token, settings.admin_token):
        raise HTTPException(status_code=403, detail="Token inválido.")


def require_admin(request: Request, token: str | None = Query(None)) -> str:
    """Dependência: valida o token (query ou header) e devolve-o."""
    supplied = token or request.headers.get("X-Admin-Token")
    _check_token(supplied)
    return supplied  # type: ignore[return-value]


def _active_run(session: Session) -> IngestRun | None:
    """Devolve uma execução em curso (e não presa), se existir."""
    cutoff = dt.datetime.now(dt.timezone.utc) - STALE_RUN_AFTER
    return session.scalar(
        select(IngestRun)
        .where(IngestRun.status == "running", IngestRun.started_at >= cutoff)
        .order_by(IngestRun.started_at.desc())
    )


def _run_pipeline_bg() -> None:
    from app.ingest.pipeline import run_pipeline

    run_pipeline()


@router.get("", response_class=HTMLResponse)
def panel(
    request: Request,
    token: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    runs = session.scalars(
        select(IngestRun).order_by(IngestRun.started_at.desc()).limit(30)
    ).all()
    running = _active_run(session) is not None
    return templates.TemplateResponse(
        "admin.html",
        _ctx(request, runs=runs, running=running, token=token),
    )


@router.post("/ingest")
def trigger_ingest(
    background_tasks: BackgroundTasks,
    request: Request,
    token: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    _check_token(token)
    if _active_run(session) is None:
        background_tasks.add_task(_run_pipeline_bg)
        status = "iniciada"
    else:
        status = "ja-a-correr"
    return RedirectResponse(url=f"/admin?token={token}&msg={status}", status_code=303)
