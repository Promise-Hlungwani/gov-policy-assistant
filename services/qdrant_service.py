from functools import lru_cache
from uuid import UUID

import httpx
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from config.settings import settings
from database.models import UserORM
from models.access import DocumentClassification
from models.document import DocumentChunk
from services.auth_service import AuthService

COLLECTION_NAME = "government_policy_chunks"


class VectorStoreError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    if not settings.qdrant_url or not settings.qdrant_api_key.get_secret_value():
        raise VectorStoreError("QDRANT_URL and QDRANT_API_KEY must be configured.")
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value(),
    )


class QdrantService:
    def _ensure_collection(self, vector_size: int) -> None:
        client = _client()
        has_classification_index = False
        if client.collection_exists(COLLECTION_NAME):
            collection = client.get_collection(COLLECTION_NAME)
            configured_size = collection.config.params.vectors.size
            if configured_size != vector_size:
                raise VectorStoreError(
                    f"Qdrant collection dimension is {configured_size}; "
                    f"the embedding model produces {vector_size}."
                )
            has_classification_index = "classification" in (
                collection.payload_schema or {}
            )
        else:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
        if not has_classification_index:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="classification",
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        *,
        classification: DocumentClassification,
        document_title: str,
        version_number: int,
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Each document chunk must have one embedding.")
        if not chunks:
            raise ValueError("Cannot index a document with no text chunks.")
        vector_size = len(vectors[0])
        if not vector_size or any(len(vector) != vector_size for vector in vectors):
            raise ValueError("Embedding vectors have inconsistent dimensions.")
        try:
            self._ensure_collection(vector_size)
            points = [
                models.PointStruct(
                    id=str(chunk.id),
                    vector=vector,
                    payload={
                        "chunk_id": str(chunk.id),
                        "document_id": str(chunk.document_id),
                        "document_version_id": str(chunk.document_version_id),
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number,
                        "text": chunk.text,
                        "classification": classification.value,
                        "document_title": document_title,
                        "version_number": version_number,
                    },
                )
                for chunk, vector in zip(chunks, vectors)
            ]
            _client().upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
        except (UnexpectedResponse, httpx.HTTPError) as exc:
            raise VectorStoreError("Qdrant rejected the document indexing request.") from exc

    def search(
        self,
        query_vector: list[float],
        *,
        user: UserORM,
        requested_classification: DocumentClassification | None = None,
        limit: int = 5,
    ) -> list[DocumentChunk]:
        auth = AuthService()
        authorized_classifications = auth.allowed_classifications(user)
        if requested_classification is not None:
            auth.require_view_permission(user, requested_classification)
            authorized_classifications = [requested_classification]
        if not authorized_classifications:
            return []
        if limit <= 0:
            raise ValueError("Search limit must be greater than zero.")
        client = _client()
        if not client.collection_exists(COLLECTION_NAME):
            return []
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="classification",
                        match=models.MatchAny(
                            any=[item.value for item in authorized_classifications]
                        ),
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
        ).points
        chunks = []
        for point in results:
            payload = point.payload
            if payload is None:
                continue
            chunks.append(
                DocumentChunk(
                    id=UUID(payload["chunk_id"]),
                    document_id=UUID(payload["document_id"]),
                    document_version_id=UUID(payload["document_version_id"]),
                    chunk_index=payload["chunk_index"],
                    text=payload["text"],
                    page_number=payload.get("page_number"),
                    vector_point_id=str(point.id),
                )
            )
        return chunks

    def delete_version(self, document_version_id: UUID) -> None:
        client = _client()
        if not client.collection_exists(COLLECTION_NAME):
            return
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_version_id",
                            match=models.MatchValue(value=str(document_version_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )
