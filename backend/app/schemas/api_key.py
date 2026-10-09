from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ApiKeyScope = Literal[
    "products:read",
    "products:create",
    "products:update",
    "products:delete",
]


def _dedupe(value: list[ApiKeyScope] | None) -> list[ApiKeyScope] | None:
    return None if value is None else list(dict.fromkeys(value))


class ApiKeyRequestCreate(BaseModel):
    """A company asking the platform team for a key."""
    name: str = Field(min_length=1, max_length=150)
    scopes: list[ApiKeyScope] = Field(default_factory=lambda: ["products:read"], min_length=1)
    purpose: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("purpose")
    @classmethod
    def trim_purpose(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("scopes")
    @classmethod
    def deduplicate_scopes(cls, value: list[ApiKeyScope]) -> list[ApiKeyScope]:
        return _dedupe(value)


class ApiKeyApprove(BaseModel):
    """Leave scopes out to grant everything requested, or pass fewer."""
    scopes: list[ApiKeyScope] | None = Field(default=None, min_length=1)

    @field_validator("scopes")
    @classmethod
    def deduplicate_scopes(cls, value: list[ApiKeyScope] | None) -> list[ApiKeyScope] | None:
        return _dedupe(value)


class ApiKeyReject(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ApiKeyRead(BaseModel):
    """Key metadata. Never contains the secret or its hash."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    name: str
    purpose: str | None
    # PENDING, APPROVED, REJECTED, ACTIVE, REVOKED, LAPSED, or EXPIRED
    status: str
    requested_scopes: list[str]
    scopes: list[str] | None
    key_prefix: str | None
    requested_by: str
    reviewed_at: datetime | None
    rejection_reason: str | None
    reveal_deadline: datetime | None
    revealed_at: datetime | None
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class PlatformApiKeyRead(ApiKeyRead):
    company_name: str | None = None
    reviewed_by: str | None
    revealed_by: str | None
    revoked_by: str | None


class ApiKeyList(BaseModel):
    items: list[ApiKeyRead]
    total: int


class PlatformApiKeyList(BaseModel):
    items: list[PlatformApiKeyRead]
    total: int


class ApiKeyRevealed(ApiKeyRead):
    # The raw key, returned exactly once.
    api_key: str
