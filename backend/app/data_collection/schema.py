"""The common shape every source is normalized into before merging.

Keeping one dataclass that all three collectors (TMDB, IMDb datasets, OMDb)
produce means the merge step never has to know source-specific field names.
Each collector is responsible for mapping its raw API/file format onto this.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawMovie:
    # Identity / cross-referencing keys. At least one of tmdb_id / imdb_id
    # must be set — this is what the merge step dedupes on.
    tmdb_id: int | None = None
    imdb_id: str | None = None

    title: str = ""
    original_title: str = ""
    year: int | None = None
    countries: list[str] = field(default_factory=list)  # ISO alpha-2 codes
    original_language: str | None = None

    director: str | None = None
    cast: list[str] = field(default_factory=list)

    synopsis: str | None = None
    synopsis_language: str | None = None

    genres: list[str] = field(default_factory=list)
    poster_url: str | None = None
    vote_average: float | None = None
    popularity: float | None = None

    # Which collector produced this record. Kept on every record (not just
    # the merged one) so the completeness report can be computed per-source
    # before any merging logic has a chance to obscure it.
    source: str = ""

    def has_synopsis(self) -> bool:
        return bool(self.synopsis and self.synopsis.strip())

    def has_director(self) -> bool:
        return bool(self.director and self.director.strip())

    def has_cast(self) -> bool:
        return bool(self.cast)
