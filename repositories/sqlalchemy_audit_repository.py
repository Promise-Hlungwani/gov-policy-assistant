from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from database.models import AuditEventORM


class SQLAlchemyAuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        *,
        actor_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID,
        details: dict[str, Any],
    ) -> None:
        self.session.add(
            AuditEventORM(
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
            )
        )
