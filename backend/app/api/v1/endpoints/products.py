from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.category import Category
from app.models.location import Location
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services.audit import log_audit

router = APIRouter(prefix="/products", tags=["products"])
writer = require_roles("ADMIN", "MANAGER")

REFS = (
    ("category_id", Category, "Category"),
    ("supplier_id", Supplier, "Supplier"),
    ("location_id", Location, "Location"),
)


def _get_product_or_404(product_id: str, db: Session) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


def _ensure_unique_sku(sku: str, db: Session, product_id: str | None = None) -> None:
    query = db.query(Product).filter(Product.sku == sku)
    if product_id is not None:
        query = query.filter(Product.id != product_id)
    if query.first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A product with this SKU already exists")


def _ensure_refs(db: Session, data: dict) -> None:
    for field, model, label in REFS:
        ref = data.get(field)
        if ref is not None and db.get(model, ref) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} not found")


@router.get("", response_model=list[ProductRead])
def list_products(
    search: str | None = Query(default=None, max_length=200),
    category_id: str | None = None,
    supplier_id: str | None = None,
    location_id: str | None = None,
    low_stock: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    query = db.query(Product)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.sku.ilike(term), Product.name.ilike(term)))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if supplier_id:
        query = query.filter(Product.supplier_id == supplier_id)
    if location_id:
        query = query.filter(Product.location_id == location_id)
    if low_stock:
        query = query.filter(Product.current_stock <= Product.reorder_level)
    return query.order_by(Product.name.asc()).offset(skip).limit(limit).all()


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: str, db: Session = Depends(get_db),
                _current_user: User = Depends(get_current_user)):
    return _get_product_or_404(product_id, db)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, request: Request,
                   db: Session = Depends(get_db), current_user: User = Depends(writer)):
    data = payload.model_dump()
    initial_stock = data.pop("initial_stock", 0) or 0
    data.pop("current_stock", None)          # never accept stock directly
    _ensure_unique_sku(data["sku"], db)
    _ensure_refs(db, data)

    product = Product(**data, current_stock=initial_stock)
    db.add(product)
    db.flush()
    log_audit(db, user_id=current_user.id, action="CREATE", entity="PRODUCT",
              entity_id=product.id, details={"sku": product.sku, "name": product.name},
              request=request)

    if initial_stock > 0:                    # opening stock gets a history row
        txn = Transaction(product_id=product.id, user_id=current_user.id, type="STOCK_IN",
                          quantity=initial_stock, reference_type="INITIAL", notes="Opening stock")
        db.add(txn)
        db.flush()
        log_audit(db, user_id=current_user.id, action="STOCK_IN", entity="TRANSACTION",
                  entity_id=txn.id,
                  details={"product_id": product.id, "quantity": initial_stock,
                           "previous_value": 0, "new_value": initial_stock,
                           "reference_type": "INITIAL"},
                  request=request)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A product with this SKU already exists")
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: str, payload: ProductUpdate, request: Request,
                   db: Session = Depends(get_db), current_user: User = Depends(writer)):
    product = _get_product_or_404(product_id, db)
    changes = payload.model_dump(exclude_unset=True)

    for f in ("sku", "name", "price", "reorder_level"):
        if changes.get(f, "") is None:
            changes.pop(f)

    if changes.get("sku") is not None:
        _ensure_unique_sku(changes["sku"], db, product_id=product.id)
    _ensure_refs(db, changes)

    before = {f: getattr(product, f) for f in changes}
    for field, value in changes.items():
        setattr(product, field, value)
    log_audit(db, user_id=current_user.id, action="UPDATE", entity="PRODUCT",
              entity_id=product.id,
              details=jsonable_encoder({"changed_fields": sorted(changes),
                                        "previous_value": before, "new_value": changes}),
              request=request)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Product could not be updated")
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: str, request: Request,
                   db: Session = Depends(get_db), current_user: User = Depends(writer)):
    product = _get_product_or_404(product_id, db)
    log_audit(db, user_id=current_user.id, action="DELETE", entity="PRODUCT",
              entity_id=product.id, details={"sku": product.sku, "name": product.name},
              request=request)
    db.delete(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()   # also discards the audit row above
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This product has transaction or adjustment history and can't be deleted.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)