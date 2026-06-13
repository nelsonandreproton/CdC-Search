"""Rotas HTML (páginas renderizadas com Jinja2)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session
from app.models import Business, Category

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter()


def _ctx(request: Request, **kwargs) -> dict:
    base = {"request": request, "site_name": settings.site_name, "target_name": settings.target_name}
    base.update(kwargs)
    return base


def _categories_with_counts(session: Session) -> list[tuple[Category, int]]:
    rows = (
        session.execute(
            select(Category, func.count(Business.id))
            .outerjoin(Business, (Business.category_id == Category.id) & (Business.active.is_(True)))
            .group_by(Category.id)
            .order_by(Category.sort_order)
        )
    ).all()
    return [(cat, count) for cat, count in rows]


@router.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    cats = _categories_with_counts(session)
    total = session.scalar(select(func.count(Business.id)).where(Business.active.is_(True))) or 0
    return templates.TemplateResponse(
        "index.html",
        _ctx(request, categories=[c for c in cats if c[1] > 0], total=total),
    )


@router.get("/categoria/{slug}", response_class=HTMLResponse)
def category_page(
    slug: str, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    cat = session.scalar(select(Category).where(Category.slug == slug))
    if cat is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    businesses = session.scalars(
        select(Business)
        .where(Business.category_id == cat.id, Business.active.is_(True))
        .order_by(Business.rating.desc().nullslast(), Business.name)
    ).all()
    return templates.TemplateResponse(
        "category.html",
        _ctx(request, category=cat, businesses=businesses),
    )


@router.get("/empresa/{slug}", response_class=HTMLResponse)
def business_page(
    slug: str, request: Request, session: Session = Depends(get_session)
) -> HTMLResponse:
    biz = session.scalar(select(Business).where(Business.slug == slug))
    if biz is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    return templates.TemplateResponse("business.html", _ctx(request, biz=biz))


@router.get("/pesquisa", response_class=HTMLResponse)
def search(
    request: Request,
    q: str = Query("", max_length=120),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    results: list[Business] = []
    term = q.strip()
    if term:
        like = f"%{term}%"
        results = list(
            session.scalars(
                select(Business)
                .where(Business.active.is_(True), Business.name.ilike(like))
                .order_by(Business.rating.desc().nullslast(), Business.name)
                .limit(100)
            ).all()
        )
    return templates.TemplateResponse(
        "search.html",
        _ctx(request, q=term, results=results),
    )
