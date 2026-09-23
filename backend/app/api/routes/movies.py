from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DbSession, Index, hits_to_scored_movies
from app.api.schemas import MovieDetail, MovieSummary, ScoredMovie
from app.embeddings.index import IndexNotBuiltError
from app.models.movie import Movie

router = APIRouter(prefix="/api/movies", tags=["movies"])


@router.get("", response_model=list[MovieSummary])
def list_mapped_movies(db: DbSession):
    """Every movie that has a position on the semantic map."""
    return db.query(Movie).filter(Movie.umap_x.isnot(None)).order_by(Movie.id).all()


@router.get("/{movie_id}", response_model=MovieDetail)
def get_movie(movie_id: int, db: DbSession):
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@router.get("/{movie_id}/similar", response_model=list[ScoredMovie])
def similar_movies(
    movie_id: int,
    db: DbSession,
    index: Index,
    top_k: int = Query(default=10, ge=1, le=50),
):
    if db.get(Movie, movie_id) is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    try:
        hits = index.similar_to(movie_id, top_k)
    except IndexNotBuiltError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return hits_to_scored_movies(db, hits)
