from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_member, require_roles
from app.db.session import get_db
from app.models.inventory_adjustment import InventoryAdjustment as Adj
from app.models.product import Product
from app.models.user import User
from app.schemas.adjustment import AdjustmentCreate, AdjustmentList, AdjustmentRead
from app.services.audit import log_audit
from app.services.stock import apply_stock_change

router = APIRouter(prefix="/adjustments", tags=["adjustments"])
writer = require_roles("ADMIN", "MANAGER")


def _read(a: Adj, pname, sku, uname) -> AdjustmentRead:
    r = AdjustmentRead.model_validate(a)
    r.product_name, r.product_sku, r.user_name = pname, sku, uname
    return r


def _base_query(db: Session, company_id: str):
    return (db.query(Adj, Product.name, Product.sku, User.name)
            .join(Product, Product.id == Adj.product_id)
            .join(User, User.id == Adj.user_id)
            .filter(Adj.company_id == company_id))


@router.get("", response_model=AdjustmentList)
def list_adjustments(
    search: str | None = None,
    product_id: str | None = None,
    user_id: str | None = None,
    reason: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_member),
):
    q = _base_query(db, user.company_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(or_(Product.name.like(like), Product.sku.like(like),
                         Adj.reason.like(like), Adj.notes.like(like)))
    if product_id:
        q = q.filter(Adj.product_id == product_id)
    if user_id:
        q = q.filter(Adj.user_id == user_id)
    if reason:
        q = q.filter(Adj.reason.like(f"%{reason.strip()}%"))
    if date_from:
        q = q.filter(Adj.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        q = q.filter(Adj.created_at < datetime.combine(date_to + timedelta(days=1), time.min))

    total = q.count()
    rows = q.order_by(Adj.created_at.desc()).offset(skip).limit(limit).all()
    return AdjustmentList(items=[_read(*r) for r in rows], total=total)


@router.get("/{adjustment_id}", response_model=AdjustmentRead)
def get_adjustment(adjustment_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_member)):
    row = _base_query(db, user.company_id).filter(Adj.id == adjustment_id).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Adjustment not found")
    return _read(*row)


@router.post("", response_model=AdjustmentRead, status_code=status.HTTP_201_CREATED)
def create_adjustment(payload: AdjustmentCreate, request: Request,
                      db: Session = Depends(get_db), user: User = Depends(writer)):
    product, before, after = apply_stock_change(db, payload.product_id, payload.quantity_change,
                                                user.company_id)

    adj = Adj(company_id=user.company_id, product_id=product.id, user_id=user.id,
              quantity_change=payload.quantity_change, reason=payload.reason, notes=payload.notes)
    db.add(adj)
    db.flush()
    log_audit(db, user_id=user.id, action="INVENTORY_ADJUSTMENT", entity="INVENTORY_ADJUSTMENT",
              entity_id=adj.id,
              details={"product_id": product.id, "sku": product.sku,
                       "quantity_change": payload.quantity_change, "reason": payload.reason,
                       "previous_value": before, "new_value": after},
              request=request)
    db.commit()
    db.refresh(adj)
    return _read(adj, product.name, product.sku, user.name)