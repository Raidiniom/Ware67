from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    category_id: Optional[str] = None
    supplier_id: Optional[str] = None
    location_id: Optional[str] = None
    unit: Optional[str] = None
    price: float = 0.0
    reorder_level: int = 0


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    sku: Optional[str] = Field(default=None, min_length=1, max_length=100)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    category_id: Optional[str] = None
    supplier_id: Optional[str] = None
    location_id: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    reorder_level: Optional[int] = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
