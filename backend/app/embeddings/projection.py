"""2D projection of the embedding space for the semantic map."""
from __future__ import annotations

import numpy as np
import umap

MIN_N_NEIGHBORS = 5
MAX_N_NEIGHBORS = 15
# Below this many points UMAP's spectral initialisation is unstable, so we
# fall back to a random init (only matters for tiny corpora / tests).
SPECTRAL_INIT_MIN_POINTS = 16


def _n_neighbors(n: int) -> int:
    """UMAP's default (15) blurs small groups together when the corpus is small:
    with 6 similar films and 15 neighbours, every film's neighbourhood spans
    several unrelated groups. Scale with sqrt(n) and cap at the default.
    """
    return min(n - 1, max(MIN_N_NEIGHBORS, min(MAX_N_NEIGHBORS, round(n**0.5))))


def project_2d(embeddings: np.ndarray, random_state: int = 42) -> np.ndarray:
    n = len(embeddings)
    if n < 3:
        return np.zeros((n, 2))
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=_n_neighbors(n),
        metric="cosine",
        init="spectral" if n >= SPECTRAL_INIT_MIN_POINTS else "random",
        random_state=random_state,
    )
    return reducer.fit_transform(embeddings)
