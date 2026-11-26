from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
