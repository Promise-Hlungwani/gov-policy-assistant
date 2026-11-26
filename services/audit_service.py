from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from models.access import UserRole
from models.document import DocumentLifecycleStatus
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
        lifecycle_status: DocumentLifecycleStatus = DocumentLifecycleStatus.CURRENT,
        superseded_version_number: int | None = None,
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
                "lifecycle_status": lifecycle_status.value,
                "superseded_version_number": superseded_version_number,
            },
        )

    def record_chat(
        self,
        *,
        actor_id: UUID,
        role: UserRole,
        question: str,
        answer: str,
        documents_accessed: list[dict[str, Any]],
        conversation_id: UUID | None,
        warnings: list[str] | None = None,
        sources_searched: list[str] | None = None,
        unavailable_sources: list[str] | None = None,
    ) -> None:
        self.repository.add(
            actor_id=actor_id,
            action="chat.answered",
            resource_type="chat_interaction",
            resource_id=conversation_id,
            details={
                "role": role.value,
                "question": question,
                "answer": answer,
                "documents_accessed": documents_accessed,
                "warnings": warnings or [],
                "sources_searched": sources_searched or [],
                "unavailable_sources": unavailable_sources or [],
            },
        )

    def record_registration_request(
        self,
        *,
        account_id: UUID,
        email: str,
    ) -> None:
        self.repository.add(
            actor_id=None,
            action="user.registration.requested",
            resource_type="user",
            resource_id=account_id,
            details={"email": email},
        )

    def record_account_approval(
        self,
        *,
        actor_id: UUID,
        account_id: UUID,
        email: str,
        role: UserRole,
    ) -> None:
        self.repository.add(
            actor_id=actor_id,
            action="user.registration.approved",
            resource_type="user",
            resource_id=account_id,
            details={"email": email, "assigned_role": role.value},
        )
