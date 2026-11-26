import logging
from dataclasses import dataclass
from uuid import UUID

from config.settings import settings
from models.access import DocumentClassification
from models.document import DocumentChunk
from services.embedding_service import EmbeddingService
from services.parser_service import DocumentParser
from services.qdrant_service import QdrantService, VectorStoreError
from utils.chunking import chunk_pages

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedIngestion:
    filename: str
    chunks: list[DocumentChunk]
    vectors: list[list[float]]


class DocumentIngestionService:
    def __init__(
        self,
        *,
        parser: DocumentParser | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: QdrantService | None = None,
    ) -> None:
        self.parser = parser or DocumentParser()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or QdrantService()

    def prepare(
        self,
        *,
        content: bytes,
        filename: str,
        document_id: UUID,
        document_version_id: UUID,
    ) -> PreparedIngestion:
        if not content:
            raise ValueError("The uploaded file is empty.")
        max_upload_size_mb = min(max(settings.max_upload_size_mb, 1), 20)
        max_size = max_upload_size_mb * 1024 * 1024
        if len(content) > max_size:
            raise ValueError(
                f"File exceeds the {max_upload_size_mb} MB upload limit."
            )

        try:
            parsed_pages = self.parser.parse_file(filename, content)
        except (ValueError, RuntimeError, OSError):
            logger.exception(
                "Text extraction failed for document version %s",
                document_version_id,
            )
            raise

        pages = [
            (page.page_number, page.section_title, page.text)
            for page in parsed_pages
            if page.text.strip()
        ]
        if not pages:
            logger.warning(
                "No extractable text found for document version %s",
                document_version_id,
            )
            raise ValueError("No readable text was found in the document.")

        try:
            chunks = chunk_pages(document_id, document_version_id, pages)
        except ValueError:
            logger.exception(
                "Text chunking failed for document version %s",
                document_version_id,
            )
            raise
        if not chunks:
            logger.warning(
                "No text chunks generated for document version %s",
                document_version_id,
            )
            raise ValueError("No searchable text chunks could be created.")

        try:
            vectors = self.embedding_service.embed_documents(chunks)
        except (RuntimeError, OSError, ValueError):
            logger.exception(
                "Embedding generation failed for document version %s",
                document_version_id,
            )
            raise
        if len(vectors) != len(chunks):
            logger.error(
                "Embedding count mismatch for %s: %d chunks, %d vectors",
                document_version_id,
                len(chunks),
                len(vectors),
            )
            raise RuntimeError("Embedding generation returned an invalid result.")

        logger.info(
            "Prepared document version %s: %d chunks",
            document_version_id,
            len(chunks),
        )
        return PreparedIngestion(
            filename=filename,
            chunks=chunks,
            vectors=vectors,
        )

    def index(
        self,
        prepared: PreparedIngestion,
        *,
        classification: DocumentClassification,
        document_title: str,
        version_number: int,
    ) -> None:
        if not prepared.chunks:
            raise ValueError("Cannot index a document with no text chunks.")
        if not document_title.strip():
            raise ValueError("Document title must not be empty.")
        if version_number < 1:
            raise ValueError("Version number must be a positive integer.")
        try:
            self.vector_store.upsert_chunks(
                prepared.chunks,
                prepared.vectors,
                classification=classification,
                document_title=document_title,
                document_filename=prepared.filename,
                version_number=version_number,
            )
        except (VectorStoreError, ValueError) as exc:
            logger.exception(
                "Qdrant indexing failed for document %s version %s",
                prepared.chunks[0].document_version_id,
                version_number,
            )
            if isinstance(exc, ValueError):
                raise VectorStoreError("Invalid vector data for Qdrant indexing.") from exc
            raise

        logger.info(
            "Indexed document version %s (%s): %d chunks",
            prepared.chunks[0].document_version_id,
            version_number,
            len(prepared.chunks),
        )

    def ingest(
        self,
        *,
        content: bytes,
        filename: str,
        document_id: UUID,
        document_version_id: UUID,
        classification: DocumentClassification,
        document_title: str,
        version_number: int,
    ) -> PreparedIngestion:
        prepared = self.prepare(
            content=content,
            filename=filename,
            document_id=document_id,
            document_version_id=document_version_id,
        )
        self.index(
            prepared,
            classification=classification,
            document_title=document_title,
            version_number=version_number,
        )
        return prepared
