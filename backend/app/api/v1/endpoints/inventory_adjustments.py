from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.product import Product
from app.models.user import User
from app.schemas.inventory_adjustment import InventoryAdjustmentCreate, InventoryAdjustmentRead

router = APIRouter(prefix="/inventory-adjustments", tags=["inventory-adjustments"])


@router.get("", response_model=list[InventoryAdjustmentRead])
def list_inventory_adjustments(
    product_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(InventoryAdjustment)
    if product_id:
        query = query.filter(InventoryAdjustment.product_id == product_id)
    return query.order_by(InventoryAdjustment.created_at.desc()).all()


@router.get("/{adjustment_id}", response_model=InventoryAdjustmentRead)
def get_inventory_adjustment(adjustment_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    adjustment = db.query(InventoryAdjustment).filter(InventoryAdjustment.id == adjustment_id).first()
    if not adjustment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory adjustment not found")
    return adjustment


@router.post("", response_model=InventoryAdjustmentRead, status_code=status.HTTP_201_CREATED)
def create_inventory_adjustment(
    payload: InventoryAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "MANAGER")),
):
    # Manual adjustments bypass a normal stock-in/stock-out reference, so — unlike
    # transactions — only ADMIN/MANAGER can create them.
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_id does not exist")

    adjustment = InventoryAdjustment(**payload.model_dump(), user_id=current_user.id)
    db.add(adjustment)
    db.commit()
    db.refresh(adjustment)
    return adjustment


@router.delete("/{adjustment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_adjustment(
    adjustment_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ADMIN")),
):
    adjustment = db.query(InventoryAdjustment).filter(InventoryAdjustment.id == adjustment_id).first()
    if not adjustment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory adjustment not found")
    db.delete(adjustment)
    db.commit()
    return None
