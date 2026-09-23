"""IMDb non-commercial datasets collector — the recall-extension source.

Why datasets instead of scraping IMDb pages
--------------------------------------------
IMDb's Terms of Service prohibit scraping its website, but IMDb publishes
official bulk datasets for non-commercial use at
https://datasets.imdbws.com/ (title.basics, title.akas, title.crew,
title.principals, name.basics). These give us title, year, genres,
director, and cast for essentially every title IMDb knows about,
including films with no synopsis and no English/French metadata at all —
which is exactly the long tail this product cares about. The trade-off:
**no plot synopsis** (that field isn't in the non-commercial dataset), so
a film found only through this source needs OMDb (see `omdb_collector.py`)
or is recorded with `synopsis=None` and surfaced as a known gap in the
completeness report.

Memory strategy
----------------
The raw files are large when decompressed (title.principals alone is
several GB). We never load a full file into memory: every "parsing"
function below takes an `Iterable[dict]` (one dict per TSV row, as
produced by `csv.DictReader`) and streams through it once, keeping only
rows relevant to our target countries. The IO wrapper (`stream_tsv_gz`)
is a thin generator so the parsing functions can be unit-tested with a
plain list of dicts, no gzip file required.
"""
from __future__ import annotations

import csv
import gzip
import logging
from collections.abc import Iterable, Iterator
from pathlib import Path

import requests

from app.data_collection.config import IMDB_DATASET_FILES, IMDB_DATASETS_BASE_URL
from app.data_collection.schema import RawMovie

logger = logging.getLogger(__name__)

NULL = "\\N"  # IMDb's null marker
TARGET_TITLE_TYPE = "movie"
MAX_CAST_MEMBERS = 10


# --------------------------------------------------------------------------
# IO layer: download + stream a .tsv.gz as an iterator of dict rows.
# --------------------------------------------------------------------------

def download_dataset(name: str, dest_dir: Path, force: bool = False) -> Path:
    filename = IMDB_DATASET_FILES[name]
    dest_path = dest_dir / filename
    if dest_path.exists() and not force:
        logger.info("IMDb dataset %s already downloaded at %s, skipping", name, dest_path)
        return dest_path

    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"{IMDB_DATASETS_BASE_URL}/{filename}"
    logger.info("Downloading IMDb dataset %s from %s", name, url)
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")
        with open(tmp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        tmp_path.rename(dest_path)
    logger.info("Downloaded %s -> %s", name, dest_path)
    return dest_path


def stream_tsv_gz(path: Path) -> Iterator[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        yield from reader


# --------------------------------------------------------------------------
# Parsing layer: pure functions over row iterables, unit-testable without IO.
# --------------------------------------------------------------------------

def find_candidate_regions(akas_rows: Iterable[dict], target_countries: set[str]) -> dict[str, set[str]]:
    """title.akas.tsv.gz -> {tconst: {region, ...}} for rows whose region is
    one of our target countries. This is the recall-driving pass: a film
    only needs ONE alternate title released in a target country to qualify.
    """
    regions_by_tconst: dict[str, set[str]] = {}
    for row in akas_rows:
        region = row.get("region", NULL)
        if region in target_countries:
            regions_by_tconst.setdefault(row["titleId"], set()).add(region)
    return regions_by_tconst


def build_movies_from_basics(basics_rows: Iterable[dict], candidate_tconsts: set[str]) -> dict[str, RawMovie]:
    """title.basics.tsv.gz -> {tconst: RawMovie} restricted to candidate ids
    and to the "movie" title type (excludes tvSeries, short, videoGame, ...).
    """
    movies: dict[str, RawMovie] = {}
    for row in basics_rows:
        tconst = row["tconst"]
        if tconst not in candidate_tconsts:
            continue
        if row.get("titleType") != TARGET_TITLE_TYPE:
            continue
        start_year = row.get("startYear", NULL)
        genres = row.get("genres", NULL)
        movies[tconst] = RawMovie(
            imdb_id=tconst,
            title=row.get("primaryTitle", ""),
            original_title=row.get("originalTitle", ""),
            year=int(start_year) if start_year != NULL and start_year.isdigit() else None,
            genres=[] if genres == NULL else genres.split(","),
            source="imdb_dataset",
        )
    return movies


def collect_director_ids(crew_rows: Iterable[dict], candidate_tconsts: set[str]) -> dict[str, list[str]]:
    """title.crew.tsv.gz -> {tconst: [nconst, ...]} of directors."""
    directors: dict[str, list[str]] = {}
    for row in crew_rows:
        tconst = row["tconst"]
        if tconst not in candidate_tconsts:
            continue
        raw_directors = row.get("directors", NULL)
        if raw_directors != NULL:
            directors[tconst] = raw_directors.split(",")
    return directors


def collect_cast_ids(principals_rows: Iterable[dict], candidate_tconsts: set[str]) -> dict[str, list[str]]:
    """title.principals.tsv.gz -> {tconst: [nconst, ...]} for actor/actress
    rows, ordered by IMDb's own `ordering` field and capped at
    MAX_CAST_MEMBERS (this file lists every credited role, not just leads).
    """
    cast_rows: dict[str, list[tuple[int, str]]] = {}
    for row in principals_rows:
        tconst = row["tconst"]
        if tconst not in candidate_tconsts:
            continue
        if row.get("category") not in {"actor", "actress"}:
            continue
        cast_rows.setdefault(tconst, []).append((int(row["ordering"]), row["nconst"]))

    cast_ids: dict[str, list[str]] = {}
    for tconst, entries in cast_rows.items():
        entries.sort(key=lambda pair: pair[0])
        cast_ids[tconst] = [nconst for _, nconst in entries[:MAX_CAST_MEMBERS]]
    return cast_ids


def resolve_names(name_basics_rows: Iterable[dict], needed_nconsts: set[str]) -> dict[str, str]:
    """name.basics.tsv.gz -> {nconst: primaryName}, restricted to the ids we
    actually need (directors + cast collected above), so this pass never
    has to hold IMDb's ~14M-person table in memory.
    """
    names: dict[str, str] = {}
    for row in name_basics_rows:
        nconst = row["nconst"]
        if nconst in needed_nconsts:
            names[nconst] = row.get("primaryName", nconst)
    return names


def attach_crew(
    movies: dict[str, RawMovie],
    director_ids: dict[str, list[str]],
    cast_ids: dict[str, list[str]],
    names: dict[str, str],
) -> None:
    """Mutates each RawMovie in place with resolved director/cast names."""
    for tconst, movie in movies.items():
        directors = director_ids.get(tconst, [])
        if directors:
            movie.director = ", ".join(names.get(n, n) for n in directors)
        movie.cast = [names.get(n, n) for n in cast_ids.get(tconst, [])]


def attach_countries(movies: dict[str, RawMovie], regions_by_tconst: dict[str, set[str]]) -> None:
    for tconst, movie in movies.items():
        movie.countries = sorted(regions_by_tconst.get(tconst, set()))


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def collect_imdb_movies(raw_dir: Path, target_countries: set[str], download: bool = True) -> list[RawMovie]:
    """Full pipeline: download (if needed) then stream through all five
    dataset files to produce RawMovie records with title/year/genres/
    director/cast/countries but NO synopsis (see module docstring).
    """
    paths = {}
    for name in IMDB_DATASET_FILES:
        paths[name] = download_dataset(name, raw_dir) if download else raw_dir / IMDB_DATASET_FILES[name]

    logger.info("Pass 1/5: scanning title.akas for target countries %s", sorted(target_countries))
    regions_by_tconst = find_candidate_regions(stream_tsv_gz(paths["title.akas"]), target_countries)
    candidate_tconsts = set(regions_by_tconst)
    logger.info("Found %d candidate titles with an alternate title in a target country", len(candidate_tconsts))

    logger.info("Pass 2/5: scanning title.basics for those candidates")
    movies = build_movies_from_basics(stream_tsv_gz(paths["title.basics"]), candidate_tconsts)
    logger.info("%d of those candidates are titleType=movie", len(movies))

    movie_tconsts = set(movies)
    logger.info("Pass 3/5: scanning title.crew for directors")
    director_ids = collect_director_ids(stream_tsv_gz(paths["title.crew"]), movie_tconsts)

    logger.info("Pass 4/5: scanning title.principals for cast")
    cast_ids = collect_cast_ids(stream_tsv_gz(paths["title.principals"]), movie_tconsts)

    needed_nconsts = set().union(*director_ids.values()) if director_ids else set()
    for ids in cast_ids.values():
        needed_nconsts.update(ids)

    logger.info("Pass 5/5: resolving %d person ids in name.basics", len(needed_nconsts))
    names = resolve_names(stream_tsv_gz(paths["name.basics"]), needed_nconsts)

    attach_crew(movies, director_ids, cast_ids, names)
    attach_countries(movies, regions_by_tconst)

    return list(movies.values())
