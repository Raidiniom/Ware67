from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.transaction import TransactionType


class TransactionCreate(BaseModel):
    product_id: str
    type: TransactionType
    quantity: int = Field(gt=0, description="Always positive; direction is carried by `type`")
    reference_type: Optional[str] = Field(default=None, max_length=50, description="e.g. PO, SO, MANUAL")
    reference_id: Optional[str] = None
    notes: Optional[str] = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    user_id: str
    type: TransactionType
    quantity: int
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
