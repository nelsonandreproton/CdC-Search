"""API JSON (leitura) — útil para integrações ou um futuro frontend."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Business, Category

router = APIRouter(prefix="/api")


def _biz_dict(b: Business) -> dict:
    return {
        "name": b.name,
        "slug": b.slug,
        "category": b.category.slug if b.category else None,
        "address": b.address,
        "phone": b.phone,
        "website": b.website,
        "rating": b.rating,
        "user_ratings_total": b.user_ratings_total,
        "nif": b.nif,
        "latitude": b.latitude,
        "longitude": b.longitude,
        "google_maps_url": b.google_maps_url,
    }


@router.get("/categories")
def list_categories(session: Session = Depends(get_session)) -> list[dict]:
    cats = session.scalars(select(Category).order_by(Category.sort_order)).all()
    return [{"slug": c.slug, "name": c.name, "icon": c.icon} for c in cats]


@router.get("/businesses")
def list_businesses(
    category: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(Business).where(Business.active.is_(True))
    if category:
        stmt = stmt.join(Category).where(Category.slug == category)
    if q:
        stmt = stmt.where(Business.name.ilike(f"%{q.strip()}%"))
    stmt = stmt.order_by(Business.name).limit(limit).offset(offset)
    items = session.scalars(stmt).all()
    return {"count": len(items), "items": [_biz_dict(b) for b in items]}
