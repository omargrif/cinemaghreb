from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.schemas import MovieSummary, ScoredMovie
from app.db.session import get_db
from app.embeddings.index import SearchHit, VibeIndex
from app.models.movie import Movie
from app.settings import settings


@lru_cache
def get_vibe_index() -> VibeIndex:
    # Cached: loading the embedding model is the slow part, do it once per process.
    return VibeIndex(settings.chroma_persist_dir)


DbSession = Annotated[Session, Depends(get_db)]
Index = Annotated[VibeIndex, Depends(get_vibe_index)]


def hits_to_scored_movies(db: Session, hits: list[SearchHit]) -> list[ScoredMovie]:
    """Resolve index hits to movies, keeping ranking order and dropping ids the
    DB no longer has (index can lag behind the DB between rebuilds).
    """
    movies = {m.id: m for m in db.query(Movie).filter(Movie.id.in_([h.movie_id for h in hits])).all()}
    return [
        ScoredMovie(movie=MovieSummary.model_validate(movies[h.movie_id]), score=h.score)
        for h in hits
        if h.movie_id in movies
    ]
