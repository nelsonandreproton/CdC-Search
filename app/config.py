"""Configuração central, carregada a partir do ambiente / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Localização-alvo
    target_name: str = "Casal de Cambra"
    target_latitude: float = 38.7995
    target_longitude: float = -9.2330
    target_radius_m: int = 2500
    target_region_code: str = "PT"
    target_language: str = "pt-PT"

    # Google Places API (New)
    google_maps_api_key: str = ""

    # LLM Gateway
    llm_gateway_url: str = "http://gateway:8080/v1"
    llm_gateway_api_key: str = "change-me-internal-key"
    llm_model: str = "llama-3.3-70b"
    llm_enabled: bool = True

    # racius.com
    racius_enabled: bool = True
    racius_request_delay_s: float = 3.0

    # Base de dados
    database_url: str = "sqlite:////data/cdc.sqlite3"

    # Web
    site_name: str = "Diretório de Casal de Cambra"
    site_base_url: str = "https://example.com"

    # Admin (painel + disparo manual da recolha). Vazio = admin desativado.
    admin_token: str = ""


settings = Settings()
