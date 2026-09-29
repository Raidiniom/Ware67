from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionList, TransactionRead
from app.services.audit import log_audit
from app.services.stock import apply_stock_change

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _read(t: Transaction, pname, sku, uname) -> TransactionRead:
    r = TransactionRead.model_validate(t)
    r.product_name, r.product_sku, r.user_name = pname, sku, uname
    return r


def _base_query(db: Session):
    return (db.query(Transaction, Product.name, Product.sku, User.name)
            .join(Product, Product.id == Transaction.product_id)
            .join(User, User.id == Transaction.user_id))


@router.get("", response_model=TransactionList)
def list_transactions(
    search: str | None = None,
    product_id: str | None = None,
    type: Literal["STOCK_IN", "STOCK_OUT"] | None = None,
    user_id: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = _base_query(db)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(or_(Product.name.like(like), Product.sku.like(like),
                         Transaction.notes.like(like), Transaction.reference_id.like(like)))
    if product_id:
        q = q.filter(Transaction.product_id == product_id)
    if type:
        q = q.filter(Transaction.type == type)
    if user_id:
        q = q.filter(Transaction.user_id == user_id)
    if reference_type:
        q = q.filter(Transaction.reference_type == reference_type.upper())
    if reference_id:
        q = q.filter(Transaction.reference_id.like(f"%{reference_id.strip()}%"))
    if date_from:
        q = q.filter(Transaction.created_at >= datetime.combine(date_from, time.min))
    if date_to:  # inclusive of the whole end day
        q = q.filter(Transaction.created_at < datetime.combine(date_to + timedelta(days=1), time.min))

    total = q.count()
    rows = q.order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()
    return TransactionList(items=[_read(*r) for r in rows], total=total)


@router.get("/{transaction_id}", response_model=TransactionRead)
def get_transaction(transaction_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    row = _base_query(db).filter(Transaction.id == transaction_id).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    return _read(*row)


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    delta = payload.quantity if payload.type == "STOCK_IN" else -payload.quantity
    product, before, after = apply_stock_change(db, payload.product_id, delta)  # locks + validates

    txn = Transaction(
        product_id=product.id,
        user_id=user.id,                    # from the JWT, never from the request body
        type=payload.type,
        quantity=payload.quantity,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        notes=payload.notes,
    )
    db.add(txn)
    db.flush()
    log_audit(db, user_id=user.id, action=payload.type, entity="TRANSACTION", entity_id=txn.id,
              details={"product_id": product.id, "sku": product.sku, "type": payload.type,
                       "quantity": payload.quantity, "previous_value": before, "new_value": after,
                       "reference_type": txn.reference_type, "reference_id": txn.reference_id},
              request=request)
    db.commit()                             # stock + history + audit land together
    db.refresh(txn)
    return _read(txn, product.name, product.sku, user.name)