"""Fusion of the three sources into one deduplicated catalogue, plus the
completeness report the project brief asks us to treat as a real result,
not just an implementation detail to hide.

Dedup strategy
--------------
1. Group by `imdb_id` when present — it's a stable key TMDB, the IMDb
   datasets, and OMDb all share, so this catches the large majority of
   overlaps for free.
2. For records with no `imdb_id` (happens occasionally on TMDB, and by
   construction never on the two IMDb-derived sources), fall back to
   fuzzy title matching *within the same release year* — bucketing by
   year keeps the O(n^2) comparison cheap and avoids false positives
   between unrelated films that happen to share a common title.

Field priority
--------------
Different sources are trusted differently per field, not as a whole
record: TMDB's synopsis/poster/genres are the most curated, but the IMDb
datasets are often the only place a director/cast credit exists at all
for a film TMDB barely covers. Countries are unioned rather than
prioritized, since broader country recall directly improves the
completeness numbers we want to report honestly.
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict

from rapidfuzz import fuzz

from app.data_collection.schema import RawMovie

TITLE_MATCH_THRESHOLD = 92

SYNOPSIS_SOURCE_PRIORITY = ["tmdb", "omdb", "imdb_dataset"]
CREW_SOURCE_PRIORITY = ["tmdb", "imdb_dataset", "omdb"]


def normalize_title(title: str) -> str:
    decomposed = unicodedata.normalize("NFKD", title or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in stripped)
    return " ".join(cleaned.split())


def _first_nonempty(movies: list[RawMovie], field_name: str, priority: list[str]):
    by_source = {m.source: m for m in movies}
    for source in priority:
        movie = by_source.get(source)
        if movie is not None:
            value = getattr(movie, field_name)
            if value:
                return value
    for movie in movies:
        value = getattr(movie, field_name)
        if value:
            return value
    return None


def group_by_identity(movies: list[RawMovie]) -> list[list[RawMovie]]:
    with_imdb_id: dict[str, list[RawMovie]] = defaultdict(list)
    without_imdb_id: list[RawMovie] = []
    for movie in movies:
        if movie.imdb_id:
            with_imdb_id[movie.imdb_id].append(movie)
        else:
            without_imdb_id.append(movie)

    groups = list(with_imdb_id.values())

    by_year: dict[int | None, list[RawMovie]] = defaultdict(list)
    for movie in without_imdb_id:
        by_year[movie.year].append(movie)

    for year_movies in by_year.values():
        used = [False] * len(year_movies)
        for i, movie_a in enumerate(year_movies):
            if used[i]:
                continue
            bucket = [movie_a]
            used[i] = True
            norm_a = normalize_title(movie_a.title)
            for j in range(i + 1, len(year_movies)):
                if used[j]:
                    continue
                norm_b = normalize_title(year_movies[j].title)
                if norm_a and norm_b and fuzz.ratio(norm_a, norm_b) >= TITLE_MATCH_THRESHOLD:
                    bucket.append(year_movies[j])
                    used[j] = True
            groups.append(bucket)

    return groups


def merge_group(group: list[RawMovie]) -> RawMovie:
    sources = sorted({m.source for m in group})
    countries: set[str] = set()
    for m in group:
        countries.update(m.countries)

    primary_title = _first_nonempty(group, "title", ["tmdb", "imdb_dataset", "omdb"]) or group[0].title
    imdb_id = next((m.imdb_id for m in group if m.imdb_id), None)
    tmdb_id = next((m.tmdb_id for m in group if m.tmdb_id), None)
    year = next((m.year for m in group if m.year), None)

    return RawMovie(
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
        title=primary_title,
        original_title=_first_nonempty(group, "original_title", ["tmdb", "imdb_dataset", "omdb"]) or primary_title,
        year=year,
        countries=sorted(countries),
        original_language=_first_nonempty(group, "original_language", ["tmdb"]),
        director=_first_nonempty(group, "director", CREW_SOURCE_PRIORITY),
        cast=_first_nonempty(group, "cast", CREW_SOURCE_PRIORITY) or [],
        synopsis=_first_nonempty(group, "synopsis", SYNOPSIS_SOURCE_PRIORITY),
        synopsis_language=_first_nonempty(group, "synopsis_language", SYNOPSIS_SOURCE_PRIORITY),
        genres=_first_nonempty(group, "genres", ["tmdb", "imdb_dataset", "omdb"]) or [],
        poster_url=_first_nonempty(group, "poster_url", ["tmdb", "omdb"]),
        vote_average=_first_nonempty(group, "vote_average", ["tmdb"]),
        popularity=_first_nonempty(group, "popularity", ["tmdb"]),
        source="+".join(sources),
    )


def merge_all_sources(movies: list[RawMovie]) -> list[RawMovie]:
    return [merge_group(group) for group in group_by_identity(movies)]


# --------------------------------------------------------------------------
# Completeness report
# --------------------------------------------------------------------------

def _pct(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 0.0


def compute_completeness_report(movies: list[RawMovie], country_names: dict[str, str]) -> dict:
    total = len(movies)
    with_synopsis = sum(1 for m in movies if m.has_synopsis())
    with_director = sum(1 for m in movies if m.has_director())
    with_cast = sum(1 for m in movies if m.has_cast())

    source_counts: dict[str, int] = defaultdict(int)
    for m in movies:
        source_counts[m.source] += 1

    per_country = {}
    for code, name in country_names.items():
        subset = [m for m in movies if code in m.countries]
        per_country[code] = {
            "name": name,
            "total": len(subset),
            "with_synopsis": sum(1 for m in subset if m.has_synopsis()),
            "with_director": sum(1 for m in subset if m.has_director()),
            "pct_missing_synopsis": _pct(len(subset) - sum(1 for m in subset if m.has_synopsis()), len(subset)),
        }

    return {
        "total_movies": total,
        "with_synopsis": with_synopsis,
        "with_director": with_director,
        "with_cast": with_cast,
        "pct_missing_synopsis": _pct(total - with_synopsis, total),
        "pct_missing_director": _pct(total - with_director, total),
        "pct_missing_cast": _pct(total - with_cast, total),
        "source_combination_counts": dict(source_counts),
        "per_country": per_country,
    }


def render_completeness_report_markdown(report: dict) -> str:
    lines = [
        "# Data completeness report",
        "",
        f"- Total movies collected: **{report['total_movies']}**",
        f"- Missing synopsis: **{report['pct_missing_synopsis']}%**",
        f"- Missing director: **{report['pct_missing_director']}%**",
        f"- Missing cast: **{report['pct_missing_cast']}%**",
        "",
        "## By source combination",
        "",
        "| Source(s) | Movies |",
        "|---|---|",
    ]
    for source, count in sorted(report["source_combination_counts"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {source} | {count} |")

    lines += ["", "## By country", "", "| Country | Movies | Missing synopsis |", "|---|---|---|"]
    for code, stats in sorted(report["per_country"].items(), key=lambda kv: -kv[1]["total"]):
        if stats["total"] == 0:
            continue
        lines.append(f"| {stats['name']} ({code}) | {stats['total']} | {stats['pct_missing_synopsis']}% |")

    return "\n".join(lines) + "\n"
