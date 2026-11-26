from typing import Any, Protocol
from uuid import UUID

from models.audit import AuditEvent


class AuditRepository(Protocol):
    def add(
        self,
        *,
        actor_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        details: dict[str, Any],
    ) -> None: ...

    def list_recent(self, limit: int) -> list[AuditEvent]: ...
