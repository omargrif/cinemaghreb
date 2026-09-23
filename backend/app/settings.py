"""Centralized environment configuration.

Every secret (API keys, DB credentials) is read from the environment via
this module — never hardcoded. See `.env.example` at the repo root for the
full list of variables a fresh clone needs to set.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tmdb_api_key: str | None = None
    omdb_api_key: str | None = None
    gemini_api_key: str | None = None

    # SQLite by default — zero-install local dev. Point this at a
    # `postgresql+psycopg://...` URL for production; nothing else changes.
    database_url: str = "sqlite:///../data/cinemaghreb.db"

    data_raw_dir: str = "../data/raw"
    data_processed_dir: str = "../data/processed"
    chroma_persist_dir: str = "../data/chroma_db"

    jwt_secret: str = "dev-secret-change-me"


settings = Settings()
