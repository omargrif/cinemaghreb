"""CLI entry point for Phase 1 data collection.

Usage (from backend/, with the venv active):

    python -m app.data_collection.run_pipeline --countries maghreb
    python -m app.data_collection.run_pipeline --countries all --skip-imdb
    python -m app.data_collection.run_pipeline --countries maghreb --limit-pages 2   # smoke test

Requires TMDB_API_KEY in `.env` (see `.env.example`). OMDB_API_KEY is
optional — without it, films found only via the IMDb datasets are kept
with `synopsis=None` instead of being backfilled.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path

from app.data_collection.config import ALL_TARGET_COUNTRIES, MAGHREB_COUNTRIES
from app.data_collection.imdb_datasets import collect_imdb_movies
from app.data_collection.merge import compute_completeness_report, merge_all_sources, render_completeness_report_markdown
from app.data_collection.omdb_collector import OMDbClient, fetch_missing_synopses
from app.data_collection.schema import RawMovie
from app.data_collection.tmdb_collector import TMDBClient, collect_tmdb_movies
from app.settings import settings

logger = logging.getLogger(__name__)

COUNTRY_SETS = {
    "maghreb": MAGHREB_COUNTRIES,
    "all": ALL_TARGET_COUNTRIES,
}


def write_csv(movies: list[RawMovie], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "tmdb_id", "imdb_id", "title", "original_title", "year", "countries",
        "original_language", "director", "cast", "synopsis", "synopsis_language",
        "genres", "poster_url", "vote_average", "popularity", "source",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in movies:
            row = {
                "tmdb_id": m.tmdb_id,
                "imdb_id": m.imdb_id,
                "title": m.title,
                "original_title": m.original_title,
                "year": m.year,
                "countries": "|".join(m.countries),
                "original_language": m.original_language,
                "director": m.director,
                "cast": "|".join(m.cast),
                "synopsis": m.synopsis,
                "synopsis_language": m.synopsis_language,
                "genres": "|".join(m.genres),
                "poster_url": m.poster_url,
                "vote_average": m.vote_average,
                "popularity": m.popularity,
                "source": m.source,
            }
            writer.writerow(row)
    logger.info("Wrote %d movies to %s", len(movies), path)


def main() -> None:
    parser = argparse.ArgumentParser(description="CineMaghreb Phase 1 data collection pipeline")
    parser.add_argument("--countries", choices=list(COUNTRY_SETS), default="maghreb")
    parser.add_argument("--skip-imdb", action="store_true", help="Skip the IMDb datasets pass (faster, less recall)")
    parser.add_argument("--skip-omdb", action="store_true", help="Skip OMDb synopsis backfill even if OMDB_API_KEY is set")
    parser.add_argument("--limit-pages", type=int, default=None, help="Cap TMDB discover pages per country (smoke testing)")
    parser.add_argument("--out-dir", default=settings.data_processed_dir)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    country_codes = COUNTRY_SETS[args.countries]
    all_movies: list[RawMovie] = []

    if not settings.tmdb_api_key:
        raise SystemExit("TMDB_API_KEY is not set. Copy .env.example to .env and fill it in.")

    tmdb_client = TMDBClient(api_key=settings.tmdb_api_key)
    max_pages = args.limit_pages or 500
    tmdb_movies, per_country_counts = collect_tmdb_movies(tmdb_client, country_codes, max_pages_per_country=max_pages)
    logger.info("TMDB: %d unique movies across %d countries", len(tmdb_movies), len(country_codes))
    for code, count in per_country_counts.items():
        logger.info("  TMDB %s (%s): %d movies", code, country_codes[code], count)
    all_movies.extend(tmdb_movies)

    if not args.skip_imdb:
        raw_dir = Path(settings.data_raw_dir) / "imdb"
        imdb_movies = collect_imdb_movies(raw_dir, set(country_codes))
        logger.info("IMDb datasets: %d candidate movies", len(imdb_movies))
        all_movies.extend(imdb_movies)

    merged = merge_all_sources(all_movies)
    logger.info("Merged: %d unique movies (from %d raw records)", len(merged), len(all_movies))

    if not args.skip_omdb and settings.omdb_api_key:
        missing = [m for m in merged if not m.has_synopsis() and m.imdb_id]
        logger.info("OMDb backfill: attempting %d movies with no synopsis", len(missing))
        omdb_client = OMDbClient(api_key=settings.omdb_api_key)
        backfilled = fetch_missing_synopses(omdb_client, [m.imdb_id for m in missing])
        for movie in merged:
            if movie.imdb_id in backfilled and not movie.has_synopsis():
                extra = backfilled[movie.imdb_id]
                movie.synopsis = extra.synopsis
                movie.synopsis_language = extra.synopsis_language
                movie.source = f"{movie.source}+omdb"

    out_dir = Path(args.out_dir)
    write_csv(merged, out_dir / "movies.csv")

    report = compute_completeness_report(merged, country_codes)
    (out_dir / "completeness_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "completeness_report.md").write_text(render_completeness_report_markdown(report), encoding="utf-8")
    logger.info("Completeness report written to %s", out_dir)


if __name__ == "__main__":
    main()
