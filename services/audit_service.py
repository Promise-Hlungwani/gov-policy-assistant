from uuid import UUID

from sqlalchemy.orm import Session

from repositories.sqlalchemy_audit_repository import SQLAlchemyAuditRepository


class AuditService:
    def __init__(self, session: Session) -> None:
        self.repository = SQLAlchemyAuditRepository(session)

    def record_upload(
        self,
        *,
        actor_id: UUID,
        document_id: UUID,
        filename: str,
        title: str,
        classification: str,
        version_number: int,
    ) -> None:
        self.repository.add(
            actor_id=actor_id,
            action="document.uploaded",
            resource_type="document",
            resource_id=document_id,
            details={
                "filename": filename,
                "title": title,
                "classification": classification,
                "version_number": version_number,
            },
        )
