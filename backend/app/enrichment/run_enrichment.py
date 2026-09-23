"""CLI entry point for Phase 2 ambiance enrichment.

Usage (from backend/, with the venv active):

    python -m app.enrichment.run_enrichment
    python -m app.enrichment.run_enrichment --limit 20   # smoke test

Requires GEMINI_API_KEY in `.env`. Only movies with a synopsis and no
ambiance tags yet are tagged, so re-running is safe and picks up where the
last run stopped. The free tier allows 20 requests/day per model, so one run
walks `FREE_TIER_MODELS` to spend each model's separate allowance (~40 films)
and then stops — run it again the next day to continue.
"""
from __future__ import annotations

import argparse
import logging

from google import genai

from app.db.session import SessionLocal
from app.enrichment.ambiance_tagger import tag_movies
from app.enrichment.config import FREE_TIER_MODELS
from app.models.movie import Movie
from app.settings import settings

logger = logging.getLogger(__name__)

COMMIT_EVERY = 20


def main() -> None:
    parser = argparse.ArgumentParser(description="CineMaghreb Phase 2 ambiance enrichment")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of movies tagged (smoke testing)")
    parser.add_argument("--delay-seconds", type=float, default=4.5, help="Delay between Gemini calls (rate limiting)")
    parser.add_argument("--model", default=None, help=f"Use one model instead of walking {FREE_TIER_MODELS}")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")

    session = SessionLocal()
    try:
        # Most popular first: the daily free-tier quota is far smaller than the
        # catalogue, so whatever `--limit` we can afford should go to the films
        # most likely to be searched for.
        candidates = (
            session.query(Movie)
            .filter(Movie.synopsis.isnot(None))
            .order_by(Movie.popularity.desc().nullslast())
            .all()
        )
        skipped_no_synopsis = session.query(Movie).filter(Movie.synopsis.is_(None)).count()
        untagged = [m for m in candidates if not m.ambiance_tags]
        to_tag = untagged[: args.limit] if args.limit else untagged

        if not to_tag:
            logger.info("Nothing to tag (skipped %d movies with no synopsis).", skipped_no_synopsis)
            return

        logger.info(
            "Tagging %d of %d untagged movies (skipping %d with no synopsis, %d already tagged)",
            len(to_tag), len(untagged), skipped_no_synopsis, len(candidates) - len(untagged),
        )

        client = genai.Client(api_key=settings.gemini_api_key)
        models = [args.model] if args.model else FREE_TIER_MODELS
        tagged = 0
        for model in models:
            remaining = [m for m in to_tag if not m.ambiance_tags]
            if not remaining:
                break
            logger.info("Tagging with %s (free tier allows 20 requests/day per model)", model)
            for movie, result in tag_movies(client, remaining, model=model, delay_seconds=args.delay_seconds):
                movie.ambiance_tags = result.tags
                movie.mood_summary = result.mood_summary
                tagged += 1
                # Commit as we go: these runs are long (daily quota cap), and an
                # interrupted one should keep the films it already tagged.
                if tagged % COMMIT_EVERY == 0:
                    session.commit()
                    logger.info("Tagged %d so far...", tagged)
        session.commit()
        logger.info(
            "Tagged %d movies. %d still untagged — re-run this command tomorrow to continue.",
            tagged, len(untagged) - tagged,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
