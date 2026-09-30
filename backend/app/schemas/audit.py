from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str | None
    user_name: str | None = None
    user_email: str | None = None
    action: str
    entity: str
    entity_id: str | None
    details: Any | None
    ip_address: str | None
    created_at: datetime | None


class AuditLogList(BaseModel):
    items: list[AuditLogRead]
    total: int