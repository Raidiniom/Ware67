from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductBase(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category_id: str | None = Field(default=None, max_length=36)
    supplier_id: str | None = Field(default=None, max_length=36)
    location_id: str | None = Field(default=None, max_length=36)
    unit: str | None = Field(default=None, max_length=50)
    price: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    reorder_level: int = Field(default=0, ge=0)

    @field_validator("sku", "name")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("description", "unit")
    @classmethod
    def optional_text_is_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category_id: str | None = Field(default=None, max_length=36)
    supplier_id: str | None = Field(default=None, max_length=36)
    location_id: str | None = Field(default=None, max_length=36)
    unit: str | None = Field(default=None, max_length=50)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    reorder_level: int | None = Field(default=None, ge=0)

    @field_validator("sku", "name")
    @classmethod
    def supplied_required_text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("description", "unit")
    @classmethod
    def supplied_optional_text_is_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
