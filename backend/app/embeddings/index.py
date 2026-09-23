"""Vector index: sentence-transformers embeddings stored in a persistent Chroma collection.

The embedder is injected (anything with `encode(list[str]) -> ndarray`) so tests
run against a tiny deterministic fake instead of downloading a ~1 GB model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings
from chromadb.errors import NotFoundError

EMBEDDING_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
COLLECTION_NAME = "movies_vibe"


class IndexNotBuiltError(RuntimeError):
    """Raised when searching before `build_index` has ever run."""


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Loads the model on first use so importing this module stays cheap."""

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model = None

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


@dataclass
class SearchHit:
    movie_id: int
    score: float  # cosine similarity, 1.0 = identical direction


class VibeIndex:
    def __init__(self, persist_dir: str, embedder: Embedder | None = None) -> None:
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._embedder = embedder or SentenceTransformerEmbedder()

    def _collection(self):
        try:
            return self._client.get_collection(COLLECTION_NAME)
        except NotFoundError as exc:
            raise IndexNotBuiltError("Vector index not built yet; run `python -m app.embeddings.build_index`") from exc

    def rebuild(self, movie_ids: list[int], texts: list[str]) -> np.ndarray:
        """Drop and recreate the collection from scratch. The 2D projection is
        refit from all embeddings on every build anyway, so there is nothing
        to gain from incremental updates at this corpus size.
        """
        embeddings = self._embedder.encode(texts)
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except NotFoundError:  # first build: nothing to delete
            pass
        collection = self._client.create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
        if movie_ids:
            collection.add(ids=[str(i) for i in movie_ids], embeddings=embeddings.tolist())
        return embeddings

    def search(self, query: str, top_k: int = 20) -> list[SearchHit]:
        embedding = self._embedder.encode([query])[0]
        return self._query(embedding.tolist(), top_k)

    def similar_to(self, movie_id: int, top_k: int = 10) -> list[SearchHit]:
        stored = self._collection().get(ids=[str(movie_id)], include=["embeddings"])
        if len(stored["ids"]) == 0:
            return []
        hits = self._query(stored["embeddings"][0].tolist(), top_k + 1)
        return [h for h in hits if h.movie_id != movie_id][:top_k]

    def _query(self, embedding: list[float], top_k: int) -> list[SearchHit]:
        collection = self._collection()
        n_results = min(top_k, collection.count())
        if n_results == 0:
            return []
        result = collection.query(query_embeddings=[embedding], n_results=n_results)
        return [
            SearchHit(movie_id=int(movie_id), score=1.0 - float(distance))
            for movie_id, distance in zip(result["ids"][0], result["distances"][0], strict=True)
        ]
