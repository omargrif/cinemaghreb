from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import DbSession, Index, hits_to_scored_movies
from app.api.schemas import ScoredMovie, VibeSearchRequest
from app.embeddings.index import IndexNotBuiltError

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/vibe", response_model=list[ScoredMovie])
def vibe_search(request: VibeSearchRequest, db: DbSession, index: Index):
    """Free-text mood query -> nearest movies, best first."""
    try:
        hits = index.search(request.query, request.top_k)
    except IndexNotBuiltError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return hits_to_scored_movies(db, hits)
