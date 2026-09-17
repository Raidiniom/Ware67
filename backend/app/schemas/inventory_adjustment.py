from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class InventoryAdjustmentCreate(BaseModel):
    product_id: str
    quantity_change: int
    reason: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("quantity_change")
    @classmethod
    def _not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("quantity_change cannot be zero")
        return v


class InventoryAdjustmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    user_id: str
    quantity_change: int
    reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
