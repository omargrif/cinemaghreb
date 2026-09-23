"""The persisted movie record.

Mirrors `app.data_collection.schema.RawMovie` field-for-field (that's what
`load_to_db.py` writes from), plus the fields Phase 2 adds on top: LLM-generated
ambiance tags/summary, and the precomputed 2D UMAP position used to render the
semantic map without recomputing the projection on every page load.
"""
from __future__ import annotations

from sqlalchemy import JSON, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # At least one of these identifies the record; both are unique when present.
    tmdb_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    imdb_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)

    title: Mapped[str] = mapped_column(String, default="")
    original_title: Mapped[str] = mapped_column(String, default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    original_language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    director: Mapped[str | None] = mapped_column(String, nullable=True)
    cast: Mapped[list[str]] = mapped_column(JSON, default=list)

    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    synopsis_language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    poster_url: Mapped[str | None] = mapped_column(String, nullable=True)
    vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    popularity: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String, default="")

    # Phase 2: ambiance enrichment + semantic map position.
    ambiance_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    mood_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    umap_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    umap_y: Mapped[float | None] = mapped_column(Float, nullable=True)
