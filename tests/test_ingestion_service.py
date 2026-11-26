import unittest
from uuid import uuid4

from models.access import DocumentClassification
from services.ingestion_service import DocumentIngestionService
from services.parser_service import ParsedPage
from services.qdrant_service import VectorStoreError


class FakeParser:
    def parse_file(self, filename: str, content: bytes) -> list[ParsedPage]:
        return [ParsedPage(page_number=1, text="A policy passage for search.")]


class FakeEmbeddingService:
    def embed_documents(self, chunks):
        return [[0.1, 0.2, 0.3] for _ in chunks]


class FakeVectorStore:
    def __init__(self) -> None:
        self.calls = []
        self.error = None

    def upsert_chunks(self, chunks, vectors, **metadata) -> None:
        self.calls.append((chunks, vectors, metadata))
        if self.error is not None:
            raise self.error


class DocumentIngestionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vector_store = FakeVectorStore()
        self.service = DocumentIngestionService(
            parser=FakeParser(),
            embedding_service=FakeEmbeddingService(),
            vector_store=self.vector_store,
        )
        self.document_id = uuid4()
        self.version_id = uuid4()

    def test_extracts_chunks_embeds_and_indexes(self) -> None:
        result = self.service.ingest(
            content=b"document bytes",
            filename="policy.pdf",
            document_id=self.document_id,
            document_version_id=self.version_id,
            classification=DocumentClassification.PUBLIC,
            document_title="Policy",
            version_number=1,
        )

        self.assertEqual(len(result.chunks), 1)
        self.assertEqual(len(result.vectors), 1)
        self.assertEqual(len(self.vector_store.calls), 1)
        self.assertEqual(
            self.vector_store.calls[0][2]["classification"],
            DocumentClassification.PUBLIC,
        )

    def test_qdrant_failure_is_logged_and_propagated(self) -> None:
        self.vector_store.error = VectorStoreError("Qdrant is unavailable.")

        with self.assertLogs("services.ingestion_service", level="ERROR"):
            with self.assertRaises(VectorStoreError):
                self.service.ingest(
                    content=b"document bytes",
                    filename="policy.pdf",
                    document_id=self.document_id,
                    document_version_id=self.version_id,
                    classification=DocumentClassification.PUBLIC,
                    document_title="Policy",
                    version_number=1,
                )
