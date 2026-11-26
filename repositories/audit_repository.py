from typing import Protocol

from models.audit import AuditEvent


class AuditRepository(Protocol):
    def add(self, event: AuditEvent) -> AuditEvent: ...

    def list_recent(self, limit: int) -> list[AuditEvent]: ...
