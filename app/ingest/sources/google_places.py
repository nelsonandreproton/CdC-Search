"""Recolha de empresas via Google Places API (New).

Usa o endpoint ``places:searchText`` com:
  - várias *queries* (uma por tipo de empresa) para maximizar a cobertura;
  - ``locationRestriction`` num círculo à volta de Casal de Cambra;
  - paginação por ``nextPageToken``.

Docs: https://developers.google.com/maps/documentation/places/web-service/text-search
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Campos pedidos (FieldMask). Manter mínimo controla o custo da API.
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.primaryType",
        "places.types",
        "places.formattedAddress",
        "places.location",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
        "places.rating",
        "places.userRatingCount",
        "places.regularOpeningHours.weekdayDescriptions",
        "places.businessStatus",
        "nextPageToken",
    ]
)

# Termos de pesquisa que cobrem os tipos de empresa típicos de uma vila.
SEARCH_QUERIES = [
    "restaurantes",
    "cafés",
    "pastelarias",
    "padarias",
    "bares",
    "supermercados",
    "mercearias",
    "talhos",
    "peixarias",
    "farmácias",
    "clínicas",
    "dentistas",
    "cabeleireiros",
    "estética",
    "ginásios",
    "oficinas automóveis",
    "stands automóveis",
    "lojas",
    "bancos",
    "imobiliárias",
    "escolas",
    "infantários",
    "hotéis",
    "alojamento local",
    "empresas",
]


@dataclass
class PlaceResult:
    place_id: str
    name: str
    primary_type: str | None
    types: list[str]
    address: str | None
    latitude: float | None
    longitude: float | None
    phone: str | None
    website: str | None
    google_maps_url: str | None
    rating: float | None
    user_ratings_total: int | None
    opening_hours: list[str] | None
    business_status: str | None = None
    raw: dict = field(default_factory=dict)


def _parse_place(p: dict) -> PlaceResult | None:
    place_id = p.get("id")
    name = (p.get("displayName") or {}).get("text")
    if not place_id or not name:
        return None
    loc = p.get("location") or {}
    hours = (p.get("regularOpeningHours") or {}).get("weekdayDescriptions")
    return PlaceResult(
        place_id=place_id,
        name=name,
        primary_type=p.get("primaryType"),
        types=p.get("types") or [],
        address=p.get("formattedAddress"),
        latitude=loc.get("latitude"),
        longitude=loc.get("longitude"),
        phone=p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber"),
        website=p.get("websiteUri"),
        google_maps_url=p.get("googleMapsUri"),
        rating=p.get("rating"),
        user_ratings_total=p.get("userRatingCount"),
        opening_hours=hours,
        business_status=p.get("businessStatus"),
        raw=p,
    )


class GooglePlacesClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.google_maps_api_key
        if not self.api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY não definido.")
        self._client = httpx.Client(timeout=30.0)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GooglePlacesClient":
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=16))
    def _post(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        resp = self._client.post(SEARCH_URL, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error("Places API %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        return resp.json()

    def search_text(self, query: str) -> list[PlaceResult]:
        """Pesquisa por texto, restrita ao círculo da localização-alvo."""
        results: list[PlaceResult] = []
        payload = {
            "textQuery": f"{query} em {settings.target_name}",
            "languageCode": settings.target_language,
            "regionCode": settings.target_region_code,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": settings.target_latitude,
                        "longitude": settings.target_longitude,
                    },
                    "radius": float(settings.target_radius_m),
                }
            },
        }
        page_token: str | None = None
        for _ in range(3):  # no máx. 3 páginas (60 resultados) por query
            if page_token:
                payload["pageToken"] = page_token
            data = self._post(payload)
            for p in data.get("places", []):
                parsed = _parse_place(p)
                if parsed:
                    results.append(parsed)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            time.sleep(2)  # nextPageToken precisa de um curto intervalo
        return results

    def collect_all(self) -> dict[str, PlaceResult]:
        """Corre todas as queries e devolve resultados desduplicados por place_id."""
        by_id: dict[str, PlaceResult] = {}
        for q in SEARCH_QUERIES:
            try:
                for r in self.search_text(q):
                    by_id.setdefault(r.place_id, r)
                logger.info("query '%s' -> total acumulado %d", q, len(by_id))
            except Exception as exc:  # noqa: BLE001
                logger.warning("query '%s' falhou: %s", q, exc)
        return by_id
