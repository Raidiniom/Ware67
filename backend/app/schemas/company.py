from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    is_active: bool
    created_at: datetime | None


class PlatformCompanyRead(CompanyRead):
    member_count: int = 0


class PlatformCompanyList(BaseModel):
    items: list[PlatformCompanyRead]
    total: int


class CompanyRename(BaseModel):
    name: str = Field(min_length=1, max_length=150)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip_name(value)


class PlatformCompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return _strip_name(value)
