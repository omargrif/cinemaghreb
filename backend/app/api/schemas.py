from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MovieSummary(BaseModel):
    """What the map and result lists need: identity, a poster, and a position."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    year: int | None
    countries: list[str]
    genres: list[str]
    ambiance_tags: list[str]
    poster_url: str | None
    umap_x: float | None
    umap_y: float | None


class MovieDetail(MovieSummary):
    original_title: str
    director: str | None
    cast: list[str]
    synopsis: str | None
    mood_summary: str | None
    vote_average: float | None


class ScoredMovie(BaseModel):
    movie: MovieSummary
    score: float


class VibeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=20, ge=1, le=100)
