from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import UserORM
from models.access import DocumentClassification, UserRole

ROLE_CLASSIFICATIONS = {
    UserRole.CITIZEN: frozenset({DocumentClassification.PUBLIC}),
    UserRole.GOVERNMENT_OFFICER: frozenset(
        {DocumentClassification.PUBLIC, DocumentClassification.INTERNAL}
    ),
    UserRole.DEPARTMENT_MANAGER: frozenset(
        {
            DocumentClassification.PUBLIC,
            DocumentClassification.INTERNAL,
            DocumentClassification.RESTRICTED,
        }
    ),
    UserRole.ADMINISTRATOR: frozenset(DocumentClassification),
}


class AuthService:
    def get_user_for_subject(self, session: Session, subject: str) -> UserORM:
        if not subject:
            raise PermissionError("An authenticated identity is required.")
        user = session.scalar(
            select(UserORM).where(
                UserORM.auth_subject == subject,
                UserORM.is_active.is_(True),
            )
        )
        if user is None:
            raise PermissionError(
                "Your account is not provisioned. Contact an administrator."
            )
        return user

    def allowed_classifications(self, user: UserORM) -> list[DocumentClassification]:
        if not user.is_active:
            raise PermissionError("Your account is inactive.")
        return sorted(ROLE_CLASSIFICATIONS[user.role], key=lambda item: item.value)

    def require_upload_permission(
        self,
        user: UserORM,
        classification: DocumentClassification,
    ) -> None:
        if classification not in self.allowed_classifications(user):
            raise PermissionError(
                f"Your role cannot upload {classification.value} documents."
            )

    def require_view_permission(
        self,
        user: UserORM,
        classification: DocumentClassification,
    ) -> None:
        if classification not in self.allowed_classifications(user):
            raise PermissionError(
                f"Your role cannot access {classification.value} documents."
            )
