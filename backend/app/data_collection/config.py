"""Shared constants for the data collection pipeline.

Country scope
-------------
The product targets Moroccan and Maghrebi cinema first, with the broader
Arab world as a secondary ring (co-productions and diaspora films are
common, e.g. a Moroccan-Egyptian-French co-production). We keep the two
rings separate so the merge step can report coverage per ring, not just
a single blended number that would hide how thin Maghreb-only data is.
"""
from __future__ import annotations

# ISO 3166-1 alpha-2 codes, TMDB's `with_origin_country` format.
MAGHREB_COUNTRIES: dict[str, str] = {
    "MA": "Morocco",
    "DZ": "Algeria",
    "TN": "Tunisia",
    "LY": "Libya",
    "MR": "Mauritania",
}

# Remaining Arab League members. Cinema output and TMDB/IMDb coverage for
# these varies a lot (Egypt has a century-old industry and decent TMDB
# coverage; Gulf states have very little), which is itself a data point
# worth surfacing in the completeness report.
ARAB_LEAGUE_COUNTRIES: dict[str, str] = {
    "EG": "Egypt",
    "LB": "Lebanon",
    "SY": "Syria",
    "IQ": "Iraq",
    "JO": "Jordan",
    "PS": "Palestine",
    "SA": "Saudi Arabia",
    "AE": "United Arab Emirates",
    "KW": "Kuwait",
    "QA": "Qatar",
    "BH": "Bahrain",
    "OM": "Oman",
    "YE": "Yemen",
    "SD": "Sudan",
    "SO": "Somalia",
    "DJ": "Djibouti",
    "KM": "Comoros",
}

ALL_TARGET_COUNTRIES: dict[str, str] = {**MAGHREB_COUNTRIES, **ARAB_LEAGUE_COUNTRIES}

# Languages we try to keep a synopsis in, in priority order. Arabic and
# French are the two languages the target catalogue is actually written
# in; English is TMDB's default fallback and is often the *only* language
# available, which is itself worth measuring.
SYNOPSIS_LANGUAGES = ["ar", "fr", "en"]

TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
OMDB_API_BASE_URL = "https://www.omdbapi.com/"

IMDB_DATASETS_BASE_URL = "https://datasets.imdbws.com"
IMDB_DATASET_FILES = {
    "title.basics": "title.basics.tsv.gz",
    "title.akas": "title.akas.tsv.gz",
    "title.crew": "title.crew.tsv.gz",
    "title.principals": "title.principals.tsv.gz",
    "name.basics": "name.basics.tsv.gz",
}

DIRECTOR_CATEGORY = "director"
ACTOR_CATEGORIES = {"actor", "actress"}
