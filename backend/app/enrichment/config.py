"""Controlled vocabulary for ambiance tagging.

Kept small and fixed (rather than letting the model invent free-form tags) so
the semantic map's facets/colors stay consistent across the whole catalogue —
the same reasoning `data_collection/config.py` uses for country sets.
"""
from __future__ import annotations

AMBIANCE_TAGS: list[str] = [
    "nostalgique",
    "mélancolique",
    "onirique",
    "contemplatif",
    "tendu",
    "chaleureux",
    "social",
    "intimiste",
    "satirique",
    "poétique",
    "cru",
    "sombre",
    "lumineux",
    "absurde",
    "politique",
    "initiatique",
    "choral",
    "âpre",
    "tendre",
    "ironique",
    "oppressant",
    "festif",
    "méditatif",
    "rebelle",
]

# Gemini free tier (AI Studio API key) — no billing setup needed, at the cost
# of a daily request cap instead of Claude's Batch API discount. The cap is
# 20 requests/day *per model*, so a run walks this list to spend each model's
# separate allowance in one go (~40 films/day). Ordered cheapest-first; both
# are plenty for picking from a 24-tag vocabulary.
FREE_TIER_MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash"]
AMBIANCE_MODEL = FREE_TIER_MODELS[0]
MIN_TAGS_PER_MOVIE = 2
MAX_TAGS_PER_MOVIE = 5
