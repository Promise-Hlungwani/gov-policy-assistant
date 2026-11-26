from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from database.models import AuditEventORM, DocumentORM, DocumentVersionORM
from models.access import DocumentClassification, UserRole
from models.document import DocumentLibraryItem, DocumentLifecycleStatus
from services.auth_service import AuthService


class DocumentLibraryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.auth = AuthService()

    def available_versions(self, *, user_id: UUID) -> list[int]:
        user = self.auth.get_active_user(self.session, user_id)
        classifications = self.auth.allowed_classifications(user)
        return list(
            self.session.scalars(
                select(DocumentVersionORM.version_number)
                .join(DocumentORM)
                .where(DocumentORM.classification.in_(classifications))
                .distinct()
                .order_by(DocumentVersionORM.version_number)
            )
        )

    def list_items(
        self,
        *,
        user_id: UUID,
        search: str = "",
        classification: DocumentClassification | None = None,
        lifecycle_status: DocumentLifecycleStatus | None = None,
        version_number: int | None = None,
        page: int = 1,
        page_size: int = 12,
    ) -> tuple[list[DocumentLibraryItem], int]:
        if page < 1 or page_size < 1:
            raise ValueError("Page and page size must be positive.")
        user = self.auth.get_active_user(self.session, user_id)
        classifications = self.auth.allowed_classifications(user)
        if classification is not None and classification not in classifications:
            raise PermissionError("This classification is not available to your role.")

        conditions = [DocumentORM.classification.in_(classifications)]
        if classification is not None:
            conditions.append(DocumentORM.classification == classification)
        if lifecycle_status is not None:
            conditions.append(
                DocumentVersionORM.lifecycle_status == lifecycle_status.value
            )
        if version_number is not None:
            conditions.append(DocumentVersionORM.version_number == version_number)
        if search.strip():
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    DocumentORM.title.ilike(pattern),
                    DocumentORM.filename.ilike(pattern),
                )
            )

        count_statement = (
            select(func.count())
            .select_from(DocumentVersionORM)
            .join(DocumentORM)
            .where(*conditions)
        )
        total = int(self.session.scalar(count_statement) or 0)
        status_priority = case(
            (DocumentVersionORM.lifecycle_status == "current", 0),
            (DocumentVersionORM.lifecycle_status == "draft", 1),
            else_=2,
        )
        rows = self.session.execute(
            select(DocumentORM, DocumentVersionORM)
            .join(DocumentVersionORM, DocumentVersionORM.document_id == DocumentORM.id)
            .where(*conditions)
            .order_by(
                status_priority,
                DocumentORM.title,
                DocumentVersionORM.version_number.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            DocumentLibraryItem(
                document_id=document.id,
                title=document.title,
                filename=version.filename,
                classification=DocumentClassification(document.classification),
                version_id=version.id,
                version_number=version.version_number,
                lifecycle_status=DocumentLifecycleStatus(version.lifecycle_status),
                index_status=version.index_status,
                created_at=version.created_at,
            )
            for document, version in rows
        ]
        return items, total


class DashboardService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.auth = AuthService()

    def metrics(self, *, user_id: UUID) -> dict[str, int]:
        user = self.auth.get_active_user(self.session, user_id)
        classifications = self.auth.allowed_classifications(user)
        total_documents = int(
            self.session.scalar(
                select(func.count(func.distinct(DocumentORM.id))).where(
                    DocumentORM.classification.in_(classifications)
                )
            )
            or 0
        )
        current_versions = int(
            self.session.scalar(
                select(func.count())
                .select_from(DocumentVersionORM)
                .join(DocumentORM)
                .where(
                    DocumentORM.classification.in_(classifications),
                    DocumentVersionORM.lifecycle_status
                    == DocumentLifecycleStatus.CURRENT.value,
                )
            )
            or 0
        )
        audit_scope = (
            []
            if user.role == UserRole.ADMINISTRATOR
            else [AuditEventORM.actor_id == user_id]
        )
        questions_asked = int(
            self.session.scalar(
                select(func.count()).where(
                    AuditEventORM.action == "chat.answered",
                    *audit_scope,
                )
            )
            or 0
        )
        audit_logs = int(
            self.session.scalar(
                select(func.count()).where(*audit_scope)
            )
            or 0
        )
        return {
            "total_documents": total_documents,
            "current_versions": current_versions,
            "questions_asked": questions_asked,
            "audit_logs": audit_logs,
        }
