from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.common import blank_to_none


class AdjustmentCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=36)
    quantity_change: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=1, max_length=150)
    notes: str | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("notes", mode="before")
    @classmethod
    def _blank(cls, v):
        return blank_to_none(v)

    @field_validator("quantity_change")
    @classmethod
    def _nonzero(cls, v):
        if v == 0:
            raise ValueError("quantity_change must not be zero")
        return v


class AdjustmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_id: str
    product_name: str | None = None
    product_sku: str | None = None
    user_id: str
    user_name: str | None = None
    quantity_change: int
    reason: str | None
    notes: str | None
    created_at: datetime | None


class AdjustmentList(BaseModel):
    items: list[AdjustmentRead]
    total: int