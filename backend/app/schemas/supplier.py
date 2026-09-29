from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.schemas.common import blank_to_none


class SupplierBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    contact_person: str | None = Field(default=None, max_length=150)
    contact_number: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None

    @field_validator("name", "contact_person", "contact_number", "email", "address", mode="before")
    @classmethod
    def _clean(cls, v):
        v = v.strip() if isinstance(v, str) else v
        return v

    @field_validator("contact_person", "contact_number", "email", "address", mode="before")
    @classmethod
    def _blank(cls, v):
        return blank_to_none(v)


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(SupplierBase):
    pass


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    contact_person: str | None
    contact_number: str | None
    email: str | None
    address: str | None
    product_count: int = 0
    created_at: datetime | None
    updated_at: datetime | None


class SupplierList(BaseModel):
    items: list[SupplierRead]
    total: int