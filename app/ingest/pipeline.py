"""Pipeline diário de recolha e atualização do diretório.

Passos:
  1. Garante categorias na BD.
  2. Recolhe empresas via Google Places API.
  3. Para cada empresa: classifica (Google -> LLM fallback), faz upsert por
     ``place_id``, e marca ``last_seen_at``.
  4. Enriquece (best-effort) com NIF/ficha do racius.com.
  5. Marca como inativas as empresas que deixaram de aparecer (soft-delete).
  6. Regista o resultado em ``IngestRun``.

Pensado para ser idempotente: correr várias vezes não duplica registos.
"""
from __future__ import annotations

import datetime as dt
import logging

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categories import CATEGORIES, OUTROS_SLUG, classify_by_google_types
from app.config import settings
from app.database import SessionLocal, init_db
from app.ingest.llm import LLMClassifier
from app.ingest.sources.google_places import GooglePlacesClient, PlaceResult
from app.ingest.sources.racius import RaciusClient
from app.models import Business, Category, IngestRun

logger = logging.getLogger(__name__)


def ensure_categories(session: Session) -> dict[str, Category]:
    """Cria/atualiza as categorias e devolve um índice slug -> Category."""
    by_slug: dict[str, Category] = {}
    for order, spec in enumerate(CATEGORIES):
        cat = session.scalar(select(Category).where(Category.slug == spec["slug"]))
        if cat is None:
            cat = Category(slug=spec["slug"])
            session.add(cat)
        cat.name = spec["name"]
        cat.icon = spec["icon"]
        cat.description = spec["description"]
        cat.sort_order = order
        by_slug[spec["slug"]] = cat
    session.flush()
    return by_slug


def _unique_slug(session: Session, name: str, place_id: str | None) -> str:
    base = slugify(name) or "empresa"
    candidate = base
    n = 2
    while True:
        existing = session.scalar(select(Business).where(Business.slug == candidate))
        if existing is None or existing.place_id == place_id:
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def _resolve_category(
    classifier: LLMClassifier, name: str, primary_type: str | None, types: list[str]
) -> str:
    ordered = ([primary_type] if primary_type else []) + types
    slug = classify_by_google_types(ordered)
    if slug:
        return slug
    # Fallback LLM (só quando a Google não chega a conclusão).
    return classifier.classify(name, ordered) or OUTROS_SLUG


def upsert_place(
    session: Session,
    place: PlaceResult,
    categories: dict[str, Category],
    classifier: LLMClassifier,
    now: dt.datetime,
) -> tuple[Business, bool]:
    """Insere ou atualiza uma empresa. Devolve (business, is_new)."""
    biz = session.scalar(select(Business).where(Business.place_id == place.place_id))
    is_new = biz is None
    if is_new:
        biz = Business(place_id=place.place_id, source="google")
        biz.slug = _unique_slug(session, place.name, place.place_id)
        biz.first_seen_at = now
        session.add(biz)

    cat_slug = _resolve_category(classifier, place.name, place.primary_type, place.types)
    biz.name = place.name
    biz.category = categories.get(cat_slug, categories[OUTROS_SLUG])
    biz.raw_types = place.types
    biz.address = place.address
    biz.latitude = place.latitude
    biz.longitude = place.longitude
    biz.phone = place.phone
    biz.website = place.website
    biz.google_maps_url = place.google_maps_url
    biz.opening_hours = place.opening_hours
    biz.rating = place.rating
    biz.user_ratings_total = place.user_ratings_total
    biz.last_seen_at = now
    biz.active = place.business_status != "CLOSED_PERMANENTLY"
    return biz, is_new


def enrich_with_racius(session: Session, businesses: list[Business]) -> int:
    """Tenta preencher NIF / link racius para empresas que ainda não têm."""
    if not settings.racius_enabled:
        return 0
    enriched = 0
    with RaciusClient() as racius:
        for biz in businesses:
            if biz.nif or biz.racius_url:
                continue
            info = racius.lookup(biz.name, settings.target_name)
            if info and (info.nif or info.racius_url):
                biz.nif = info.nif or biz.nif
                biz.racius_url = info.racius_url or biz.racius_url
                if biz.source == "google":
                    biz.source = "merged"
                enriched += 1
    return enriched


def run_pipeline() -> IngestRun:
    """Executa o pipeline completo e devolve o registo IngestRun."""
    init_db()
    now = dt.datetime.now(dt.timezone.utc)
    session = SessionLocal()
    run = IngestRun(started_at=now, status="running")
    session.add(run)
    session.commit()

    log_lines: list[str] = []
    try:
        categories = ensure_categories(session)
        session.commit()

        if not settings.google_maps_api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY não definido — nada a recolher.")

        with GooglePlacesClient() as gp:
            places = gp.collect_all()
        log_lines.append(f"Google Places: {len(places)} empresas distintas.")

        classifier = LLMClassifier()
        new_count = 0
        touched: list[Business] = []
        seen_ids: set[str] = set()
        for place in places.values():
            biz, is_new = upsert_place(session, place, categories, classifier, now)
            touched.append(biz)
            if place.place_id:
                seen_ids.add(place.place_id)
            new_count += int(is_new)
        session.commit()
        log_lines.append(f"Novas: {new_count}; atualizadas: {len(touched) - new_count}.")

        enriched = enrich_with_racius(session, touched)
        session.commit()
        log_lines.append(f"Enriquecidas via racius: {enriched}.")

        # Soft-delete: empresas Google que não apareceram nesta recolha.
        stale = session.scalars(
            select(Business).where(
                Business.source != "racius",
                Business.active.is_(True),
                Business.place_id.is_not(None),
                Business.place_id.notin_(seen_ids) if seen_ids else False,
            )
        ).all()
        for biz in stale:
            biz.active = False
        if stale:
            log_lines.append(f"Marcadas inativas: {len(stale)}.")

        run.status = "ok"
        run.new_count = new_count
        run.updated_count = len(touched) - new_count
        run.seen_count = len(touched)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline falhou")
        run.status = "error"
        log_lines.append(f"ERRO: {exc}")
    finally:
        run.finished_at = dt.datetime.now(dt.timezone.utc)
        run.log = "\n".join(log_lines)
        session.commit()
        result = run
        session.close()
    return result
