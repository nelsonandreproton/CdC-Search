"""Modelos da base de dados."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str] = mapped_column(String(16), default="📍")
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=100)

    businesses: Mapped[list["Business"]] = relationship(back_populates="category")


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (UniqueConstraint("place_id", name="uq_business_place_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identidade / origem
    place_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="google")  # google | racius | merged

    # Dados principais
    name: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(280), unique=True, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), index=True, nullable=True)
    raw_types: Mapped[list | None] = mapped_column(JSON, default=list)

    # Contactos / localização
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    google_maps_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    opening_hours: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Métricas Google
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_ratings_total: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Enriquecimento racius
    nif: Mapped[str | None] = mapped_column(String(20), nullable=True)
    racius_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Estado / auditoria
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    category: Mapped["Category | None"] = relationship(back_populates="businesses")


class IngestRun(Base):
    """Registo de cada execução do pipeline diário."""

    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running | ok | error
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    seen_count: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[str] = mapped_column(Text, default="")
