"""Load the merged Phase 1 CSV output into the database.

Usage (from backend/, with the venv active):

    python -m app.data_collection.load_to_db
    python -m app.data_collection.load_to_db --csv ../data/processed/movies.csv

Upserts by `tmdb_id` first, then `imdb_id`, so re-running after a fresh
pipeline run updates existing rows (new synopsis, updated popularity, ...)
instead of duplicating them.
"""
from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.models.movie import Movie
from app.settings import settings

logger = logging.getLogger(__name__)

CSV_FIELDS = [
    "tmdb_id", "imdb_id", "title", "original_title", "year", "countries",
    "original_language", "director", "cast", "synopsis", "synopsis_language",
    "genres", "poster_url", "vote_average", "popularity", "source",
]


def _split(value: str) -> list[str]:
    return [v for v in value.split("|") if v] if value else []


def _int_or_none(value: str) -> int | None:
    return int(value) if value else None


def _float_or_none(value: str) -> float | None:
    return float(value) if value else None


def _find_existing(session: Session, tmdb_id: int | None, imdb_id: str | None) -> Movie | None:
    if tmdb_id is not None:
        existing = session.query(Movie).filter_by(tmdb_id=tmdb_id).one_or_none()
        if existing is not None:
            return existing
    if imdb_id is not None:
        return session.query(Movie).filter_by(imdb_id=imdb_id).one_or_none()
    return None


def load_csv(csv_path: Path, session: Session | None = None) -> tuple[int, int]:
    """Upsert every row of `csv_path` into the `movies` table.

    Returns (created, updated) counts. Accepts an injected session for tests;
    opens/commits/closes its own otherwise.
    """
    owns_session = session is None
    if owns_session:
        init_db()
        session = SessionLocal()

    created = 0
    updated = 0
    try:
        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tmdb_id = _int_or_none(row["tmdb_id"])
                imdb_id = row["imdb_id"] or None
                existing = _find_existing(session, tmdb_id, imdb_id)

                movie = existing or Movie()
                movie.tmdb_id = tmdb_id
                movie.imdb_id = imdb_id
                movie.title = row["title"]
                movie.original_title = row["original_title"]
                movie.year = _int_or_none(row["year"])
                movie.countries = _split(row["countries"])
                movie.original_language = row["original_language"] or None
                movie.director = row["director"] or None
                movie.cast = _split(row["cast"])
                movie.synopsis = row["synopsis"] or None
                movie.synopsis_language = row["synopsis_language"] or None
                movie.genres = _split(row["genres"])
                movie.poster_url = row["poster_url"] or None
                movie.vote_average = _float_or_none(row["vote_average"])
                movie.popularity = _float_or_none(row["popularity"])
                movie.source = row["source"]

                if existing is None:
                    session.add(movie)
                    created += 1
                else:
                    updated += 1
        session.commit()
    finally:
        if owns_session:
            session.close()

    logger.info("Loaded %d new movies, updated %d existing", created, updated)
    return created, updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Phase 1 CSV output into the database")
    parser.add_argument("--csv", default=None, help="Path to movies.csv (default: <data_processed_dir>/movies.csv)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    csv_path = Path(args.csv) if args.csv else Path(settings.data_processed_dir) / "movies.csv"
    if not csv_path.exists():
        raise SystemExit(f"CSV not found at {csv_path}. Run run_pipeline.py first.")

    load_csv(csv_path)


if __name__ == "__main__":
    main()
