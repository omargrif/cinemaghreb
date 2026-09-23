"""TMDB collector — the primary structured source.

Strategy: TMDB's `/discover/movie` can filter by a single origin country per
call, so we query one country at a time (this also gives us a natural
per-country movie count for the completeness report, which a single
multi-country query would hide). We collect just the ids in this pass,
union them across all target countries (a movie can be a co-production
counted under several countries), and only then fetch full details —
this avoids paying for a details call twice for the same film.

Details are fetched with `append_to_response=credits,translations,
external_ids` so each film costs exactly one extra HTTP call regardless of
how many languages/cast members/crew we need out of it.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Iterable

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.data_collection.config import SYNOPSIS_LANGUAGES, TMDB_API_BASE_URL
from app.data_collection.schema import RawMovie

logger = logging.getLogger(__name__)

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
MAX_TMDB_PAGES = 500  # hard cap enforced by the TMDB API itself


class TMDBRateLimitError(Exception):
    """Raised on HTTP 429 so tenacity can back off and retry."""


class TMDBClient:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        base_url: str = TMDB_API_BASE_URL,
        request_delay_seconds: float = 0.05,
    ) -> None:
        if not api_key:
            raise ValueError("TMDB API key is required (set TMDB_API_KEY in .env)")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.base_url = base_url
        self.request_delay_seconds = request_delay_seconds

    @retry(
        retry=retry_if_exception_type(TMDBRateLimitError),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
    )
    def get(self, path: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        params["api_key"] = self.api_key
        response = self.session.get(f"{self.base_url}{path}", params=params, timeout=15)
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", 1))
            time.sleep(retry_after)
            raise TMDBRateLimitError(f"429 on {path}")
        response.raise_for_status()
        if self.request_delay_seconds:
            time.sleep(self.request_delay_seconds)
        return response.json()


def discover_country_ids(client: TMDBClient, country_code: str, max_pages: int = MAX_TMDB_PAGES) -> set[int]:
    """Return every TMDB movie id whose origin country is `country_code`."""
    ids: set[int] = set()
    page = 1
    total_pages = 1
    while page <= min(total_pages, max_pages):
        data = client.get(
            "/discover/movie",
            params={
                "with_origin_country": country_code,
                "page": page,
                "sort_by": "popularity.desc",
                "include_adult": "false",
            },
        )
        results = data.get("results", [])
        ids.update(movie["id"] for movie in results)
        total_pages = data.get("total_pages", 1)
        logger.debug("TMDB discover %s page %d/%d -> %d results", country_code, page, total_pages, len(results))
        page += 1
    logger.info("TMDB discover: %s -> %d movies (origin country filter)", country_code, len(ids))
    return ids


def _pick_synopsis(translations: list[dict], fallback_overview: str, fallback_language: str) -> tuple[str | None, str | None]:
    """Prefer Arabic, then French, then English; fall back to whatever the
    default details call returned (usually English or the original language).
    """
    by_lang = {t["iso_639_1"]: t.get("data", {}).get("overview", "") for t in translations}
    for lang in SYNOPSIS_LANGUAGES:
        text = by_lang.get(lang)
        if text and text.strip():
            return text.strip(), lang
    if fallback_overview and fallback_overview.strip():
        return fallback_overview.strip(), fallback_language
    return None, None


def parse_movie_details(details: dict, requested_language: str = "en") -> RawMovie:
    credits = details.get("credits", {}) or {}
    crew = credits.get("crew", []) or []
    cast = credits.get("cast", []) or []
    translations = (details.get("translations", {}) or {}).get("translations", []) or []
    external_ids = details.get("external_ids", {}) or {}

    director_names = [person["name"] for person in crew if person.get("job") == "Director"]
    synopsis, synopsis_lang = _pick_synopsis(translations, details.get("overview", ""), requested_language)

    release_date = details.get("release_date") or ""
    year = int(release_date[:4]) if len(release_date) >= 4 and release_date[:4].isdigit() else None

    poster_path = details.get("poster_path")

    return RawMovie(
        tmdb_id=details.get("id"),
        imdb_id=details.get("imdb_id") or external_ids.get("imdb_id"),
        title=details.get("title", ""),
        original_title=details.get("original_title", ""),
        year=year,
        countries=[c["iso_3166_1"] for c in details.get("production_countries", [])],
        original_language=details.get("original_language"),
        director=", ".join(director_names) if director_names else None,
        cast=[member["name"] for member in cast[:10]],
        synopsis=synopsis,
        synopsis_language=synopsis_lang,
        genres=[g["name"] for g in details.get("genres", [])],
        poster_url=f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None,
        vote_average=details.get("vote_average"),
        popularity=details.get("popularity"),
        source="tmdb",
    )


def fetch_movie_details(client: TMDBClient, tmdb_id: int) -> RawMovie | None:
    try:
        data = client.get(
            f"/movie/{tmdb_id}",
            params={"append_to_response": "credits,translations,external_ids"},
        )
    except requests.HTTPError as exc:
        logger.warning("TMDB details fetch failed for id=%s: %s", tmdb_id, exc)
        return None
    return parse_movie_details(data)


def find_by_imdb_id(client: TMDBClient, imdb_id: str) -> int | None:
    """Look up a TMDB id from an IMDb id (`tt...`). Used to check whether a
    film discovered only via the IMDb dataset actually exists in TMDB under
    an origin country our discover queries didn't catch.
    """
    data = client.get(f"/find/{imdb_id}", params={"external_source": "imdb_id"})
    results = data.get("movie_results", [])
    return results[0]["id"] if results else None


def collect_tmdb_movies(
    client: TMDBClient,
    country_codes: Iterable[str],
    max_pages_per_country: int = MAX_TMDB_PAGES,
) -> tuple[list[RawMovie], dict[str, int]]:
    """Collect every movie across the given countries, deduped by tmdb id.

    Returns the list of parsed movies plus a per-country id count (before
    dedup) so the pipeline can report "N movies found for country X" even
    though the same film may be counted under several countries.
    """
    ids_per_country: dict[str, set[int]] = {}
    for country_code in country_codes:
        ids_per_country[country_code] = discover_country_ids(client, country_code, max_pages_per_country)

    all_ids: set[int] = set()
    for ids in ids_per_country.values():
        all_ids |= ids

    movies: list[RawMovie] = []
    for tmdb_id in all_ids:
        movie = fetch_movie_details(client, tmdb_id)
        if movie is not None:
            movies.append(movie)

    per_country_counts = {country: len(ids) for country, ids in ids_per_country.items()}
    return movies, per_country_counts
