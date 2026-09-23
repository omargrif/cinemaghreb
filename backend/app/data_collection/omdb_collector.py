"""OMDb collector — synopsis fallback for films IMDb-dataset-only films.

The IMDb non-commercial datasets have no plot field. For a film we only
found via `imdb_datasets.py` (i.e. TMDB doesn't have it), OMDb
(omdbapi.com) is a legal, ToS-compliant way to get a plot summary by
IMDb id — it's a licensed aggregation, not a scrape. Free tier is capped
at 1,000 requests/day, so this is used sparingly and only for the gap
TMDB + IMDb datasets can't fill, not as a bulk source.
"""
from __future__ import annotations

import logging

import requests

from app.data_collection.config import OMDB_API_BASE_URL
from app.data_collection.schema import RawMovie

logger = logging.getLogger(__name__)


class OMDbClient:
    def __init__(self, api_key: str, session: requests.Session | None = None, base_url: str = OMDB_API_BASE_URL) -> None:
        if not api_key:
            raise ValueError("OMDb API key is required (set OMDB_API_KEY in .env)")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.base_url = base_url

    def get_by_imdb_id(self, imdb_id: str) -> dict | None:
        response = self.session.get(self.base_url, params={"i": imdb_id, "apikey": self.api_key, "plot": "full"}, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("Response") == "False":
            logger.debug("OMDb has no record for %s: %s", imdb_id, data.get("Error"))
            return None
        return data


def _split_list(value: str | None) -> list[str]:
    if not value or value == "N/A":
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_omdb_record(data: dict) -> RawMovie:
    year_raw = (data.get("Year") or "")[:4]
    plot = data.get("Plot")
    return RawMovie(
        imdb_id=data.get("imdbID"),
        title=data.get("Title", ""),
        original_title=data.get("Title", ""),
        year=int(year_raw) if year_raw.isdigit() else None,
        countries=_split_list(data.get("Country")),
        director=data.get("Director") if data.get("Director") not in (None, "N/A") else None,
        cast=_split_list(data.get("Actors")),
        synopsis=plot if plot and plot != "N/A" else None,
        synopsis_language="en",  # OMDb plots are English-only
        genres=_split_list(data.get("Genre")),
        poster_url=data.get("Poster") if data.get("Poster") not in (None, "N/A") else None,
        source="omdb",
    )


def fetch_missing_synopses(client: OMDbClient, imdb_ids: list[str]) -> dict[str, RawMovie]:
    """Look up each imdb_id and return {imdb_id: RawMovie} for the ones OMDb
    actually knows about. Callers use this to backfill synopsis-only gaps,
    not to overwrite fields already collected from a richer source.
    """
    results: dict[str, RawMovie] = {}
    for imdb_id in imdb_ids:
        data = client.get_by_imdb_id(imdb_id)
        if data is not None:
            results[imdb_id] = parse_omdb_record(data)
    logger.info("OMDb: resolved %d/%d requested imdb ids", len(results), len(imdb_ids))
    return results
