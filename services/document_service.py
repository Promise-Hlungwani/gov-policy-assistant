from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from config.settings import settings
from database.models import DocumentChunkORM, DocumentORM, DocumentVersionORM
from models.access import DocumentClassification
from models.document import DocumentVersion
from repositories.sqlalchemy_document_repository import SQLAlchemyDocumentRepository
from services.audit_service import AuditService
from services.auth_service import AuthService
from services.embedding_service import EmbeddingService
from services.parser_service import DocumentParser
from services.qdrant_service import QdrantService, VectorStoreError
from utils.chunking import chunk_pages


class DocumentService:
    def __init__(
        self,
        session: Session,
        *,
        parser: DocumentParser | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: QdrantService | None = None,
    ) -> None:
        self.session = session
        self.repository = SQLAlchemyDocumentRepository(session)
        self.auth = AuthService()
        self.audit = AuditService(session)
        self.parser = parser or DocumentParser()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or QdrantService()

    def upload(
        self,
        *,
        content: bytes,
        filename: str,
        title: str,
        version_number: int,
        classification: DocumentClassification,
        auth_subject: str,
    ) -> DocumentVersion:
        safe_filename = Path(filename).name
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Enter a document title.")
        if len(normalized_title) > 500:
            raise ValueError("Document title must be 500 characters or fewer.")
        if version_number < 1:
            raise ValueError("Version number must be a positive integer.")
        if not content:
            raise ValueError("The uploaded file is empty.")
        max_size = settings.max_upload_size_mb * 1024 * 1024
        if len(content) > max_size:
            raise ValueError(
                f"File exceeds the {settings.max_upload_size_mb} MB upload limit."
            )

        extension = Path(safe_filename).suffix.lower()
        mime_type_by_extension = {
            ".pdf": "application/pdf",
            ".docx": (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        }
        mime_type = mime_type_by_extension.get(extension)
        if mime_type is None:
            raise ValueError("Upload a PDF or DOCX document.")
        parsed_pages = self.parser.parse_file(safe_filename, content)
        page_text = [
            (page.page_number, page.text)
            for page in parsed_pages
            if page.text.strip()
        ]
        if not page_text:
            raise ValueError("No readable text was found in the document.")

        with self.session.begin():
            actor = self.auth.get_user_for_subject(self.session, auth_subject)
            self.auth.require_upload_permission(actor, classification)

            document = self.repository.get_for_owner_and_title(
                actor.id, normalized_title
            )
            if document is None:
                document = DocumentORM(
                    id=uuid4(),
                    title=normalized_title,
                    filename=safe_filename,
                    mime_type=mime_type,
                    classification=classification,
                    owner_id=actor.id,
                )
                self.repository.add_document(document)
            elif document.classification != classification:
                raise PermissionError(
                    "A document's classification cannot change between versions."
                )

            if self.repository.has_version(document.id, version_number):
                raise ValueError(
                    f"Version {version_number} already exists for this document."
                )

            version = DocumentVersionORM(
                id=uuid4(),
                document_id=document.id,
                version_number=version_number,
                filename=safe_filename,
                checksum=sha256(content).hexdigest(),
                source_file_key=safe_filename,
                created_by=actor.id,
                index_status="pending",
            )
            self.repository.add_version(version)
            document.filename = safe_filename
            document.mime_type = mime_type

            chunks = chunk_pages(
                document.id,
                version.id,
                page_text,
            )
            if not chunks:
                raise ValueError("No searchable text chunks could be created.")
            vectors = self.embedding_service.embed_documents(chunks)
            self.repository.add_chunks(
                [
                    DocumentChunkORM(
                        id=chunk.id,
                        document_version_id=version.id,
                        chunk_index=chunk.chunk_index,
                        page_number=chunk.page_number,
                        text=chunk.text,
                        vector_point_id=str(chunk.id),
                    )
                    for chunk in chunks
                ]
            )
            self.audit.record_upload(
                actor_id=actor.id,
                document_id=document.id,
                filename=safe_filename,
                title=normalized_title,
                classification=classification.value,
                version_number=version_number,
            )
            version_id = version.id

        try:
            self.vector_store.upsert_chunks(
                chunks,
                vectors,
                classification=classification,
                document_title=normalized_title,
                version_number=version_number,
            )
        except VectorStoreError:
            with self.session.begin():
                stored_version = self.repository.get_version(version_id)
                if stored_version is not None:
                    stored_version.index_status = "failed"
            raise
        with self.session.begin():
            stored_version = self.repository.get_version(version_id)
            if stored_version is None:
                raise RuntimeError("Uploaded document version was not saved.")
            stored_version.index_status = "indexed"
            result = DocumentVersion.model_validate(stored_version)
        return result
