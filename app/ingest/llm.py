"""Categorização via LLM gateway (fallback à classificação determinística).

Só é chamado quando o mapeamento por tipos da Google não chega a conclusão.
Liga-se ao free-llm-gateway por uma API OpenAI-compatible, na rede interna do
Docker. Envia apenas texto público (nome + tipos da empresa).

Degrada com elegância: qualquer falha devolve a categoria "outros".
"""
from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.categories import OUTROS_SLUG, category_slugs
from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM = (
    "És um classificador de empresas de um diretório local português. "
    "Recebes o nome e os tipos de uma empresa e respondes APENAS com o slug "
    "da categoria mais adequada, escolhido da lista fornecida. "
    "Responde em JSON: {\"slug\": \"<slug>\"}."
)


class LLMClassifier:
    def __init__(self) -> None:
        self.enabled = settings.llm_enabled
        self._client: OpenAI | None = None
        if self.enabled:
            self._client = OpenAI(
                base_url=settings.llm_gateway_url,
                api_key=settings.llm_gateway_api_key,
            )

    def classify(self, name: str, types: list[str] | None) -> str:
        """Devolve um slug de categoria válido (ou 'outros')."""
        valid = set(category_slugs())
        if not self.enabled or self._client is None:
            return OUTROS_SLUG
        slugs_list = ", ".join(sorted(valid))
        user = (
            f"Empresa: {name}\n"
            f"Tipos (Google): {', '.join(types or []) or 'desconhecidos'}\n"
            f"Categorias possíveis (slugs): {slugs_list}\n"
            "Escolhe a melhor."
        )
        try:
            resp = self._client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                max_tokens=50,
            )
            content = (resp.choices[0].message.content or "").strip()
            slug = self._extract_slug(content)
            if slug in valid:
                return slug
            logger.debug("LLM devolveu slug inválido %r para '%s'", slug, name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM classify falhou para '%s': %s", name, exc)
        return OUTROS_SLUG

    @staticmethod
    def _extract_slug(content: str) -> str:
        content = content.strip().strip("`")
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "slug" in data:
                return str(data["slug"]).strip()
        except json.JSONDecodeError:
            pass
        # fallback: a resposta pode ser só o slug em texto
        return content.split()[0].strip().strip('"').strip("{}").strip() if content else ""
