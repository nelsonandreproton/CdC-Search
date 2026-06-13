"""Utilitários de deduplicação / correspondência difusa de nomes."""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

# Formas jurídicas / termos genéricos que não distinguem empresas.
_STOPWORDS = {
    "lda",
    "ltda",
    "sa",
    "unipessoal",
    "sociedade",
    "comercio",
    "comercial",
    "servicos",
    "the",
    "and",
    "de",
    "da",
    "do",
    "e",
}


def normalize(text: str | None) -> str:
    """Minúsculas, sem acentos, sem pontuação, sem formas jurídicas."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    tokens = [t for t in text.split() if t not in _STOPWORDS]
    return " ".join(tokens).strip()


def names_match(a: str, b: str, threshold: int = 88) -> bool:
    """True se dois nomes de empresa forem provavelmente a mesma entidade."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    return fuzz.token_sort_ratio(na, nb) >= threshold
