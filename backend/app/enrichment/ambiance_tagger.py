"""Ambiance tagging via the Google Gemini API.

This runs offline, once per movie, as part of the data pipeline. We use
Gemini's free tier (an AI Studio API key) rather than Claude's Batch API:
no billing setup required, at the cost of no batch discount and a modest
rate limit — so calls are made sequentially with a delay between them (see
`tag_movies`) instead of submitted as one batch job.

Structured output (`response_schema` with `tags` items constrained via
`enum`) keeps the model close to the controlled vocabulary. Gemini's schema
enforcement is looser than Claude's strict structured output, though, so
`_parse_response` also filters the result against `AMBIANCE_TAGS` as a
safety net rather than trusting the enum alone.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from google.genai import types

from app.enrichment.config import (
    AMBIANCE_MODEL,
    AMBIANCE_TAGS,
    MAX_TAGS_PER_MOVIE,
    MIN_TAGS_PER_MOVIE,
)
from app.models.movie import Movie

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Tu es un critique de cinéma spécialiste du cinéma maghrébin et arabe. "
    "Pour chaque film décrit, choisis entre {min} et {max} tags qui décrivent "
    "son ambiance/atmosphère générale, uniquement parmi ce vocabulaire fixe : "
    "{vocab}. N'invente jamais de tag hors de cette liste. Ajoute aussi un "
    "résumé d'ambiance d'une phrase (pas un résumé de l'intrigue), en français."
).format(min=MIN_TAGS_PER_MOVIE, max=MAX_TAGS_PER_MOVIE, vocab=", ".join(AMBIANCE_TAGS))

MAX_CONSECUTIVE_ERRORS = 5

AMBIANCE_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "tags": {
            "type": "ARRAY",
            "items": {"type": "STRING", "enum": AMBIANCE_TAGS},
        },
        "mood_summary": {"type": "STRING"},
    },
    "required": ["tags", "mood_summary"],
}


@dataclass
class AmbianceResult:
    tags: list[str]
    mood_summary: str


def _movie_prompt(movie: Movie) -> str:
    lines = [f"Titre : {movie.title} ({movie.year or 'année inconnue'})"]
    if movie.director:
        lines.append(f"Réalisateur : {movie.director}")
    if movie.genres:
        lines.append(f"Genres : {', '.join(movie.genres)}")
    lines.append(f"Synopsis : {movie.synopsis}")
    return "\n".join(lines)


def _generation_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=AMBIANCE_RESPONSE_SCHEMA,
    )


def _parse_response(raw_text: str | None) -> AmbianceResult | None:
    try:
        data = json.loads(raw_text)
        tags = [t for t in data["tags"] if t in AMBIANCE_TAGS][:MAX_TAGS_PER_MOVIE]
        if len(tags) < MIN_TAGS_PER_MOVIE:
            return None
        return AmbianceResult(tags=tags, mood_summary=data["mood_summary"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def tag_movie(client, movie: Movie, model: str = AMBIANCE_MODEL) -> AmbianceResult | None:
    if not movie.synopsis:
        raise ValueError(f"Movie {movie.id} has no synopsis to tag")
    response = client.models.generate_content(
        model=model,
        contents=_movie_prompt(movie),
        config=_generation_config(),
    )
    result = _parse_response(response.text)
    if result is None:
        logger.warning("Could not parse ambiance result for movie id=%s: %r", movie.id, response.text)
    return result


def tag_movies(
    client,
    movies: list[Movie],
    model: str = AMBIANCE_MODEL,
    delay_seconds: float = 4.5,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_consecutive_errors: int = MAX_CONSECUTIVE_ERRORS,
) -> Iterator[tuple[Movie, AmbianceResult]]:
    """Tags movies one at a time, yielding each result as it arrives.

    Yields rather than returning a dict so the caller can persist progress
    as it goes: the free-tier daily cap makes these runs long, and an
    interrupted run should not throw away everything it had tagged.

    `delay_seconds` paces calls to stay under the per-minute rate limit. A
    single movie whose call fails or whose response is unparseable is
    skipped, not fatal to the run — but a run of consecutive API errors
    means the daily quota is spent (or the key is bad), so we stop instead
    of hammering the API once per remaining movie. Untagged movies are
    picked up by the next run.
    """
    tagged = 0
    consecutive_errors = 0
    for i, movie in enumerate(movies):
        if i > 0:
            sleep_fn(delay_seconds)
        try:
            result = tag_movie(client, movie, model=model)
        except Exception:
            logger.exception("Gemini call failed for movie id=%s", movie.id)
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                logger.error(
                    "Stopping after %d consecutive API errors (quota exhausted?). "
                    "Tagged %d movies; re-run later to continue.",
                    consecutive_errors, tagged,
                )
                return
            continue
        consecutive_errors = 0
        if result is not None:
            tagged += 1
            yield movie, result
