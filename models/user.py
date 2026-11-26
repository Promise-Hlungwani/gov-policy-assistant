from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.access import UserRole


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
