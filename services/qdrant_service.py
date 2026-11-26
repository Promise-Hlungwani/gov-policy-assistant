from functools import lru_cache
from uuid import UUID

import httpx
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from config.settings import settings
from database.models import UserORM
from models.access import DocumentClassification
from models.document import DocumentChunk, KnowledgeSourceType
from services.auth_service import AuthService

UPLOADED_COLLECTION_NAME = "uploaded_documents"
GOVERNMENT_REPOSITORY_COLLECTION_NAME = "government_repository"
GOVERNMENT_WEB_COLLECTION_NAME = "government_web_sources"
LEGACY_UPLOADED_COLLECTION_NAME = "government_policy_chunks"


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
    def _ensure_collection(self, collection_name: str, vector_size: int) -> None:
        client = _client()
        has_classification_index = False
        if client.collection_exists(collection_name):
            collection = client.get_collection(collection_name)
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
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
        if (
            collection_name == UPLOADED_COLLECTION_NAME
            and not has_classification_index
        ):
            client.create_payload_index(
                collection_name=collection_name,
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
        document_filename: str,
        version_number: int | None,
        collection_name: str = UPLOADED_COLLECTION_NAME,
        source_type: KnowledgeSourceType = KnowledgeSourceType.UPLOADED_DOCUMENT,
        source_url: str | None = None,
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Each document chunk must have one embedding.")
        if not chunks:
            raise ValueError("Cannot index a document with no text chunks.")
        vector_size = len(vectors[0])
        if not vector_size or any(len(vector) != vector_size for vector in vectors):
            raise ValueError("Embedding vectors have inconsistent dimensions.")
        expected_collections = {
            KnowledgeSourceType.UPLOADED_DOCUMENT: UPLOADED_COLLECTION_NAME,
            KnowledgeSourceType.GOVERNMENT_REPOSITORY: (
                GOVERNMENT_REPOSITORY_COLLECTION_NAME
            ),
            KnowledgeSourceType.GOVERNMENT_WEBSITE: GOVERNMENT_WEB_COLLECTION_NAME,
        }
        if expected_collections[source_type] != collection_name:
            raise ValueError("Knowledge source type does not match its collection.")
        if source_type == KnowledgeSourceType.GOVERNMENT_WEBSITE and not source_url:
            raise ValueError("Government website chunks must include their source URL.")
        try:
            self._ensure_collection(collection_name, vector_size)
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
                        "section_title": chunk.section_title,
                        "text": chunk.text,
                        "classification": classification.value,
                        "source_type": source_type.value,
                        "source_url": source_url,
                        "document_title": document_title,
                        "document_filename": document_filename,
                        "version_number": version_number,
                    },
                )
                for chunk, vector in zip(chunks, vectors)
            ]
            _client().upsert(
                collection_name=collection_name,
                points=points,
                wait=True,
            )
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
        chunks = self._search_collection(
            UPLOADED_COLLECTION_NAME,
            query_vector,
            limit=limit,
            source_type=KnowledgeSourceType.UPLOADED_DOCUMENT,
            authorized_classifications=authorized_classifications,
        )
        legacy_chunks = self._search_collection(
            LEGACY_UPLOADED_COLLECTION_NAME,
            query_vector,
            limit=limit,
            source_type=KnowledgeSourceType.UPLOADED_DOCUMENT,
            authorized_classifications=authorized_classifications,
        )
        unique_chunks = {chunk.id: chunk for chunk in [*chunks, *legacy_chunks]}
        return sorted(
            unique_chunks.values(),
            key=lambda chunk: chunk.similarity or 0.0,
            reverse=True,
        )[:limit]

    def search_government_repository(
        self,
        query_vector: list[float],
        *,
        user: UserORM,
        limit: int = 5,
    ) -> list[DocumentChunk]:
        self._require_active_user(user)
        return self._search_collection(
            GOVERNMENT_REPOSITORY_COLLECTION_NAME,
            query_vector,
            limit=limit,
            source_type=KnowledgeSourceType.GOVERNMENT_REPOSITORY,
        )

    def search_government_web_sources(
        self,
        query_vector: list[float],
        *,
        user: UserORM,
        limit: int = 5,
    ) -> list[DocumentChunk]:
        self._require_active_user(user)
        return self._search_collection(
            GOVERNMENT_WEB_COLLECTION_NAME,
            query_vector,
            limit=limit,
            source_type=KnowledgeSourceType.GOVERNMENT_WEBSITE,
        )

    @staticmethod
    def _require_active_user(user: UserORM) -> None:
        if not user.is_active:
            raise PermissionError("An active account is required to search sources.")

    @staticmethod
    def _search_collection(
        collection_name: str,
        query_vector: list[float],
        *,
        limit: int,
        source_type: KnowledgeSourceType,
        authorized_classifications: list[DocumentClassification] | None = None,
    ) -> list[DocumentChunk]:
        if limit <= 0:
            raise ValueError("Search limit must be greater than zero.")
        try:
            client = _client()
            if not client.collection_exists(collection_name):
                return []
            query_filter = None
            if authorized_classifications is not None:
                if not authorized_classifications:
                    return []
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="classification",
                            match=models.MatchAny(
                                any=[item.value for item in authorized_classifications]
                            ),
                        )
                    ]
                )
            results = client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            ).points
        except (UnexpectedResponse, httpx.HTTPError) as exc:
            raise VectorStoreError("Qdrant search request failed.") from exc
        chunks = []
        for point in results:
            payload = point.payload
            if payload is None:
                continue
            try:
                page_number = payload.get("page_number")
                payload_source_type = KnowledgeSourceType(
                    payload.get("source_type", source_type.value)
                )
                if payload_source_type != source_type:
                    raise ValueError("Source payload does not match its collection.")
                chunks.append(
                    DocumentChunk(
                        id=UUID(payload["chunk_id"]),
                        document_id=UUID(payload["document_id"]),
                        document_version_id=UUID(payload["document_version_id"]),
                        chunk_index=payload["chunk_index"],
                        text=payload["text"],
                        classification=DocumentClassification(
                            payload.get("classification", "public")
                        ),
                        page_number=page_number,
                        section_title=payload.get("section_title")
                        or (
                            f"Page {page_number}"
                            if page_number is not None
                            else "Document body"
                        ),
                        vector_point_id=str(point.id),
                        document_title=payload.get("document_title")
                        or payload.get("filename", "Policy document"),
                        document_filename=payload.get("document_filename")
                        or payload.get("filename")
                        or payload.get("document_title", "Unknown"),
                        version_number=payload.get("version_number"),
                        source_type=payload_source_type,
                        source_url=payload.get("source_url"),
                        similarity=float(point.score or 0.0),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise VectorStoreError("Qdrant returned an invalid source payload.") from exc
        return chunks

    def delete_version(self, document_version_id: UUID) -> None:
        client = _client()
        for collection_name in (
            UPLOADED_COLLECTION_NAME,
            LEGACY_UPLOADED_COLLECTION_NAME,
        ):
            if not client.collection_exists(collection_name):
                continue
            client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_version_id",
                                match=models.MatchValue(
                                    value=str(document_version_id)
                                ),
                            )
                        ]
                    )
                ),
                wait=True,
            )

    def delete_public_source(self, collection_name: str, source_url: str) -> None:
        if collection_name not in {
            GOVERNMENT_REPOSITORY_COLLECTION_NAME,
            GOVERNMENT_WEB_COLLECTION_NAME,
        }:
            raise ValueError("Only public knowledge collections can be refreshed.")
        try:
            client = _client()
            if not client.collection_exists(collection_name):
                return
            client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="source_url",
                                match=models.MatchValue(value=source_url),
                            )
                        ]
                    )
                ),
                wait=True,
            )
        except (UnexpectedResponse, httpx.HTTPError) as exc:
            raise VectorStoreError(
                "Could not refresh the approved public source."
            ) from exc
