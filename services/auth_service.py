from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import UserORM
from models.access import DocumentClassification, UserRole
from utils.passwords import verify_password

ACCESS_DENIED_MESSAGE = (
    "Access denied. You are not authorized to access this document."
)

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


class AccountPendingError(PermissionError):
    pass


class AuthService:
    def authenticate(
        self,
        session: Session,
        email: str,
        password: str,
    ) -> UserORM | None:
        normalized_email = email.strip().lower()
        user = session.scalar(
            select(UserORM).where(
                UserORM.email == normalized_email,
            )
        )
        if user is None:
            verify_password(password, None)
            return None
        if not verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            raise AccountPendingError(
                "Your account is awaiting administrator approval."
            )
        return user

    def get_active_user(self, session: Session, user_id: UUID) -> UserORM:
        user = session.get(UserORM, user_id)
        if user is None or not user.is_active:
            raise PermissionError(ACCESS_DENIED_MESSAGE)
        return user

    def allowed_classifications(self, user: UserORM) -> list[DocumentClassification]:
        if not user.is_active:
            raise PermissionError(ACCESS_DENIED_MESSAGE)
        return sorted(ROLE_CLASSIFICATIONS[user.role], key=lambda item: item.value)

    def require_upload_permission(
        self,
        user: UserORM,
        classification: DocumentClassification,
    ) -> None:
        if classification not in self.allowed_classifications(user):
            raise PermissionError(ACCESS_DENIED_MESSAGE)

    def require_view_permission(
        self,
        user: UserORM,
        classification: DocumentClassification,
    ) -> None:
        if classification not in self.allowed_classifications(user):
            raise PermissionError(ACCESS_DENIED_MESSAGE)
