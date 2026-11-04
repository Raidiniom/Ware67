from datetime import datetime
from pydantic import BaseModel


class DayPoint(BaseModel):
    date: str
    units: int
    transactions: int


class TopProduct(BaseModel):
    product_id: str
    sku: str
    name: str
    units: int


class InboundEvent(BaseModel):
    id: str
    created_at: datetime | None
    product_name: str
    product_sku: str
    quantity: int
    reference_type: str | None
    reference_id: str | None
    source: str


class InboundDashboard(BaseModel):
    days: int
    units_in: int
    transactions: int
    series: list[DayPoint]
    top_products: list[TopProduct]
    recent: list[InboundEvent]
