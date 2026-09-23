import numpy as np

VOCAB = ["exil", "nostalgie", "fête", "police", "mer", "désert"]


class FakeEmbedder:
    """Bag-of-words over a tiny vocabulary: texts sharing words are close."""

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = np.array(
            [[text.lower().count(word) for word in VOCAB] for text in texts], dtype=float
        ) + 1e-3
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
