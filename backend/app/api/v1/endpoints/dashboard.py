from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_member
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.dashboard import DashboardLowStockItem, DashboardMovement, DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

LIST_SIZE = 8


def _recent_movements(db: Session, company_id: str) -> list[DashboardMovement]:
    transactions = (
        db.query(Transaction, Product.name, Product.sku, User.name, ApiKey.name)
        .join(Product, Product.id == Transaction.product_id)
        .outerjoin(User, User.id == Transaction.user_id)
        .outerjoin(ApiKey, ApiKey.id == Transaction.api_key_id)
        .filter(Transaction.company_id == company_id)
        .order_by(Transaction.created_at.desc())
        .limit(LIST_SIZE)
        .all()
    )
    adjustments = (
        db.query(InventoryAdjustment, Product.name, Product.sku, User.name)
        .join(Product, Product.id == InventoryAdjustment.product_id)
        .join(User, User.id == InventoryAdjustment.user_id)
        .filter(InventoryAdjustment.company_id == company_id)
        .order_by(InventoryAdjustment.created_at.desc())
        .limit(LIST_SIZE)
        .all()
    )

    movements = [
        DashboardMovement(
            id=t.id,
            kind="TRANSACTION",
            label="Stock in" if t.type == "STOCK_IN" else "Stock out",
            product_name=product_name,
            product_sku=sku,
            quantity_change=t.quantity if t.type == "STOCK_IN" else -t.quantity,
            actor=user_name or key_name,
            created_at=t.created_at,
        )
        for t, product_name, sku, user_name, key_name in transactions
    ] + [
        DashboardMovement(
            id=a.id,
            kind="ADJUSTMENT",
            label=a.reason or "Adjustment",
            product_name=product_name,
            product_sku=sku,
            quantity_change=a.quantity_change,
            actor=user_name,
            created_at=a.created_at,
        )
        for a, product_name, sku, user_name in adjustments
    ]
    movements.sort(key=lambda m: m.created_at or datetime.min, reverse=True)
    return movements[:LIST_SIZE]


@router.get("/summary", response_model=DashboardSummary)
def read_summary(db: Session = Depends(get_db), user: User = Depends(get_current_member)):
    low = Product.current_stock <= Product.reorder_level
    product_count, units, value, low_count, out_count = (
        db.query(
            func.count(Product.id),
            func.coalesce(func.sum(Product.current_stock), 0),
            func.coalesce(func.sum(Product.current_stock * Product.price), 0),
            func.coalesce(func.sum(case((low, 1), else_=0)), 0),
            func.coalesce(func.sum(case((Product.current_stock == 0, 1), else_=0)), 0),
        )
        .filter(Product.company_id == user.company_id)
        .one()
    )
    low_items = (
        db.query(Product)
        .filter(Product.company_id == user.company_id, low)
        .order_by(Product.current_stock.asc(), Product.name.asc())
        .limit(LIST_SIZE)
        .all()
    )
    return DashboardSummary(
        # MySQL returns SUM() as a Decimal.
        product_count=product_count,
        units_in_stock=int(units),
        low_stock_count=int(low_count),
        out_of_stock_count=int(out_count),
        stock_value=Decimal(str(value)).quantize(Decimal("0.01")),
        low_stock_items=[DashboardLowStockItem.model_validate(p) for p in low_items],
        recent_movements=_recent_movements(db, user.company_id),
    )
