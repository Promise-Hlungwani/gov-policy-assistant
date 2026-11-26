from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import DocumentChunkORM, DocumentORM, DocumentVersionORM
from models.document import DocumentLifecycleStatus


class SQLAlchemyDocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_owner_and_title(
        self, owner_id: UUID, title: str
    ) -> DocumentORM | None:
        return self.session.scalar(
            select(DocumentORM).where(
                DocumentORM.owner_id == owner_id,
                DocumentORM.title == title,
            )
        )

    def has_version(self, document_id: UUID, version_number: int) -> bool:
        return (
            self.session.scalar(
                select(DocumentVersionORM.id).where(
                    DocumentVersionORM.document_id == document_id,
                    DocumentVersionORM.version_number == version_number,
                )
            )
            is not None
        )

    def get_current_version(self, document_id: UUID) -> DocumentVersionORM | None:
        return self.session.scalar(
            select(DocumentVersionORM).where(
                DocumentVersionORM.document_id == document_id,
                DocumentVersionORM.lifecycle_status
                == DocumentLifecycleStatus.CURRENT.value,
            )
        )

    def get_version_statuses(
        self, version_ids: set[UUID]
    ) -> dict[UUID, DocumentLifecycleStatus]:
        if not version_ids:
            return {}
        rows = self.session.execute(
            select(
                DocumentVersionORM.id,
                DocumentVersionORM.lifecycle_status,
            ).where(DocumentVersionORM.id.in_(version_ids))
        )
        return {
            version_id: DocumentLifecycleStatus(status)
            for version_id, status in rows
        }

    def add_document(self, document: DocumentORM) -> None:
        self.session.add(document)
        self.session.flush()

    def add_version(self, version: DocumentVersionORM) -> None:
        self.session.add(version)
        self.session.flush()

    def add_chunks(self, chunks: list[DocumentChunkORM]) -> None:
        self.session.add_all(chunks)
        self.session.flush()

    def get_version(self, version_id: UUID) -> DocumentVersionORM | None:
        return self.session.get(DocumentVersionORM, version_id)
