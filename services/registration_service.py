import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import UserORM
from models.access import UserRole
from services.audit_service import AuditService
from services.auth_service import ACCESS_DENIED_MESSAGE
from utils.passwords import hash_password

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegistrationService:
    def register(
        self,
        session: Session,
        *,
        email: str,
        display_name: str,
        password: str,
    ) -> UUID:
        normalized_email = email.strip().lower()
        normalized_name = display_name.strip()
        if len(normalized_email) > 320 or not _EMAIL_PATTERN.fullmatch(
            normalized_email
        ):
            raise ValueError("Enter a valid email address.")
        if not normalized_name:
            raise ValueError("Enter your full name.")
        if len(normalized_name) > 200:
            raise ValueError("Name must be 200 characters or fewer.")

        password_hash = hash_password(password)
        try:
            with session.begin():
                existing_user = session.scalar(
                    select(UserORM.id).where(
                        func.lower(UserORM.email) == normalized_email
                    )
                )
                if existing_user is not None:
                    raise ValueError(
                        "An account with that email address already exists."
                    )

                user = UserORM(
                    auth_subject=f"local:{normalized_email}",
                    email=normalized_email,
                    display_name=normalized_name,
                    password_hash=password_hash,
                    role=UserRole.CITIZEN,
                    is_active=False,
                )
                session.add(user)
                session.flush()
                user_id = user.id
                AuditService(session).record_registration_request(
                    account_id=user.id,
                    email=normalized_email,
                )
        except IntegrityError as exc:
            raise ValueError(
                "An account with that email address already exists."
            ) from exc
        return user_id

    def list_pending(self, session: Session) -> list[UserORM]:
        return list(
            session.scalars(
                select(UserORM)
                .where(UserORM.is_active.is_(False))
                .order_by(UserORM.created_at, UserORM.email)
            )
        )

    def approve(
        self,
        session: Session,
        *,
        user_id: UUID,
        role: UserRole,
        approver_id: UUID,
    ) -> None:
        with session.begin():
            approver = session.get(UserORM, approver_id)
            if (
                approver is None
                or not approver.is_active
                or approver.role != UserRole.ADMINISTRATOR
            ):
                raise PermissionError(ACCESS_DENIED_MESSAGE)
            user = session.get(UserORM, user_id)
            if user is None or user.is_active:
                raise ValueError("This account is no longer awaiting approval.")
            user.role = role
            user.is_active = True
            AuditService(session).record_account_approval(
                actor_id=approver.id,
                account_id=user.id,
                email=user.email,
                role=role,
            )
