from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DashboardLowStockItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sku: str
    name: str
    unit: str | None
    current_stock: int
    reorder_level: int


class DashboardMovement(BaseModel):
    id: str
    kind: str  # TRANSACTION or ADJUSTMENT
    label: str  # "Stock in", "Stock out", or the adjustment's reason
    product_name: str
    product_sku: str
    quantity_change: int  # signed: negative means stock left
    actor: str | None
    created_at: datetime | None


class DashboardSummary(BaseModel):
    product_count: int
    units_in_stock: int
    low_stock_count: int  # at or below the reorder level, same as the low_stock filter
    out_of_stock_count: int
    stock_value: Decimal  # current stock at selling price: products have no cost price
    low_stock_items: list[DashboardLowStockItem]
    recent_movements: list[DashboardMovement]
