from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from config.settings import settings
from models.document import DocumentChunk

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


class EmbeddingService:
    @property
    def vector_size(self) -> int:
        dimension = _load_model().get_sentence_embedding_dimension()
        if dimension is None:
            raise RuntimeError("The configured embedding model has no vector dimension.")
        return dimension

    def embed_documents(self, chunks: list[DocumentChunk]) -> list[list[float]]:
        if not chunks:
            return []
        vectors = _load_model().encode(
            [chunk.text for chunk in chunks],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        query = query.strip()
        if not query:
            raise ValueError("Query text must not be empty.")
        vector = _load_model().encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector.tolist()
