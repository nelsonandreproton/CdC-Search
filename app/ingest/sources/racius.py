"""Enriquecimento best-effort a partir do racius.com.

O racius.com agrega informação pública de empresas portuguesas (NIF, morada,
CAE). Este módulo faz uma pesquisa por nome + localidade e tenta extrair o NIF
e o link da ficha da empresa.

IMPORTANTE / avisos:
  - É *scraping* e, por isso, frágil: a estrutura do site pode mudar e o site
    pode bloquear pedidos automáticos. Toda a recolha falha com elegância
    (devolve ``None``) e nunca interrompe o pipeline.
  - Respeitamos o site: User-Agent identificável e atraso configurável entre
    pedidos (``RACIUS_REQUEST_DELAY_S``).
  - Se preferires não depender de scraping, define ``RACIUS_ENABLED=false``.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.racius.com/pesquisa/?q={q}"
USER_AGENT = "CdC-Search/1.0 (+diretorio Casal de Cambra; contacto via website)"
NIF_RE = re.compile(r"\b(\d{9})\b")


@dataclass
class RaciusInfo:
    nif: str | None = None
    racius_url: str | None = None
    address: str | None = None


class RaciusClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=20.0,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-PT,pt;q=0.9"},
            follow_redirects=True,
        )
        self._last_request = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RaciusClient":
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        wait = settings.racius_request_delay_s - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def lookup(self, name: str, locality: str | None = None) -> RaciusInfo | None:
        """Procura uma empresa por nome (+ localidade) e devolve info se encontrada."""
        query = name if not locality else f"{name} {locality}"
        try:
            self._throttle()
            resp = self._client.get(SEARCH_URL.format(q=quote_plus(query)))
            if resp.status_code != 200:
                logger.debug("racius pesquisa %s -> HTTP %s", query, resp.status_code)
                return None
            return self._parse_search(resp.text, name)
        except Exception as exc:  # noqa: BLE001
            logger.debug("racius lookup falhou para '%s': %s", query, exc)
            return None

    def _parse_search(self, html: str, name: str) -> RaciusInfo | None:
        """Extrai o primeiro resultado plausível da página de pesquisa.

        Heurístico e defensivo: se a estrutura mudar, devolve ``None``.
        """
        soup = BeautifulSoup(html, "lxml")
        # Os resultados costumam ser links para /empresa/... ; pegamos o 1.º.
        for a in soup.select("a[href*='/empresa/'], a[href*='/empresas/']"):
            href = a.get("href", "")
            if not href:
                continue
            url = href if href.startswith("http") else f"https://www.racius.com{href}"
            nif_match = NIF_RE.search(href) or NIF_RE.search(a.get_text(" ", strip=True))
            return RaciusInfo(
                nif=nif_match.group(1) if nif_match else None,
                racius_url=url,
                address=None,
            )
        return None
