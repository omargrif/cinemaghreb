"""Builds the text a movie is embedded from.

The mood summary and ambiance tags come first on purpose: a raw synopsis
encodes plot ("three friends cross Marrakech at night"), while the LLM-written
mood text encodes atmosphere, which is what a vibe query ("mélancolique,
nostalgique") actually matches against.
"""
from __future__ import annotations

from app.models.movie import Movie


def build_embedding_text(movie: Movie) -> str:
    parts: list[str] = []
    if movie.mood_summary:
        parts.append(movie.mood_summary)
    if movie.ambiance_tags:
        parts.append("Ambiance : " + ", ".join(movie.ambiance_tags))
    if movie.genres:
        parts.append("Genres : " + ", ".join(movie.genres))
    if movie.synopsis:
        parts.append(movie.synopsis)
    return "\n".join(parts)


def is_embeddable(movie: Movie) -> bool:
    """Movies with neither a synopsis nor a mood summary would be embedded from
    a title alone, which just adds noise to the map — leave them off it.
    """
    return bool(movie.synopsis or movie.mood_summary)
