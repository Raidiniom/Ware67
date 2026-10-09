from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ApiKeyScope = Literal[
    "products:read",
    "products:create",
    "products:update",
    "products:delete",
]


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    scopes: list[ApiKeyScope] = Field(default_factory=lambda: ["products:read"], min_length=1)
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("scopes")
    @classmethod
    def deduplicate_scopes(cls, value: list[ApiKeyScope]) -> list[ApiKeyScope]:
        return list(dict.fromkeys(value))

    # A bare "2026-12-31T00:00:00" is ambiguous (whose midnight?), so require
    # an explicit offset instead of silently assuming UTC.
    @field_validator("expires_at")
    @classmethod
    def expires_at_needs_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("must include a timezone, e.g. 2026-12-31T00:00:00Z")
        return value


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    created_by: str
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyRead):
    api_key: str
