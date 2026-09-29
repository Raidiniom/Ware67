from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.common import blank_to_none


class TransactionCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=36)
    type: Literal["STOCK_IN", "STOCK_OUT"]
    quantity: int = Field(gt=0, le=1_000_000)
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @field_validator("reference_type", "reference_id", "notes", mode="before")
    @classmethod
    def _blank(cls, v):
        return blank_to_none(v)

    @field_validator("reference_type")
    @classmethod
    def _upper(cls, v):
        return v.upper() if v else v


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_id: str
    product_name: str | None = None
    product_sku: str | None = None
    user_id: str
    user_name: str | None = None
    type: str
    quantity: int
    reference_type: str | None
    reference_id: str | None
    notes: str | None
    created_at: datetime | None


class TransactionList(BaseModel):
    items: list[TransactionRead]
    total: int