"""Local multilingual embeddings via Sentence Transformers (no API key, cost 0)."""
import os
from typing import Protocol

DEFAULT_MODEL = "intfloat/multilingual-e5-small"


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """E5 model: documents get the 'passage: ' prefix, queries get 'query: '. Vectors are L2-normalized.

    Fails loudly if the model cannot be loaded; never falls back to mock vectors.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL") or DEFAULT_MODEL
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("sentence-transformers is not installed: pip install sentence-transformers") from exc
        self._model = SentenceTransformer(self.model_name)
        self.dimensions = int(self._model.get_sentence_embedding_dimension())

    def _encode(self, texts: list[str], prefix: str) -> list[list[float]]:
        vecs = self._model.encode([prefix + t for t in texts], normalize_embeddings=True,
                                  batch_size=32, show_progress_bar=False)
        return [v.tolist() for v in vecs]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, "passage: ")

    def embed_query(self, question: str) -> list[float]:
        return self._encode([question], "query: ")[0]
