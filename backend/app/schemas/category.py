from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryBase(BaseModel):
    name: str = Field(max_length=150)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v

    @field_validator("description")
    @classmethod
    def clean_desc(cls, v):
        return v.strip() or None if v else None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    pass


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None
    product_count: int = 0
    created_at: datetime | None
    updated_at: datetime | None


class CategoryList(BaseModel):
    items: list[CategoryRead]
    total: int


class CategoryProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sku: str
    name: str
    current_stock: int