"""CLI entry point: rebuild the vector index and the 2D map positions.

Usage (from backend/, with the venv active):

    python -m app.embeddings.build_index

Run it again whenever movies or their ambiance tags change. The first run
downloads the multilingual sentence-transformers model (~1 GB).
"""
from __future__ import annotations

import logging

from app.db.session import SessionLocal, init_db
from app.embeddings.index import VibeIndex
from app.embeddings.projection import project_2d
from app.embeddings.text_builder import build_embedding_text, is_embeddable
from app.models.movie import Movie
from app.settings import settings

logger = logging.getLogger(__name__)


def build_index(session, index: VibeIndex) -> int:
    movies = session.query(Movie).all()
    embeddable = [m for m in movies if is_embeddable(m)]
    logger.info(
        "Indexing %d movies (%d left off the map: no synopsis or mood summary)",
        len(embeddable), len(movies) - len(embeddable),
    )

    for movie in movies:
        movie.umap_x = None
        movie.umap_y = None

    if embeddable:
        embeddings = index.rebuild([m.id for m in embeddable], [build_embedding_text(m) for m in embeddable])
        coords = project_2d(embeddings)
        for movie, (x, y) in zip(embeddable, coords, strict=True):
            movie.umap_x = float(x)
            movie.umap_y = float(y)

    session.commit()
    return len(embeddable)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    init_db()
    session = SessionLocal()
    try:
        build_index(session, VibeIndex(settings.chroma_persist_dir))
    finally:
        session.close()


if __name__ == "__main__":
    main()
