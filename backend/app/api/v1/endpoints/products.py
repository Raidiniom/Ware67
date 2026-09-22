from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services.audit import log_audit

router = APIRouter(prefix="/products", tags=["products"])


def _get_product_or_404(product_id: str, db: Session) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


def _ensure_unique_sku(sku: str, db: Session, product_id: str | None = None) -> None:
    query = db.query(Product).filter(Product.sku == sku)
    if product_id is not None:
        query = query.filter(Product.id != product_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this SKU already exists",
        )


@router.get("", response_model=list[ProductRead])
def list_products(
    search: str | None = Query(default=None, max_length=200),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    query = db.query(Product)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.sku.ilike(term), Product.name.ilike(term)))
    return query.order_by(Product.name.asc()).offset(skip).limit(limit).all()


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return _get_product_or_404(product_id, db)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "MANAGER")),
):
    _ensure_unique_sku(payload.sku, db)
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    log_audit(
        db,
        user_id=current_user.id,
        action="CREATE",
        entity="products",
        entity_id=product.id,
        details={"sku": product.sku, "name": product.name},
    )
    return product


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "MANAGER")),
):
    product = _get_product_or_404(product_id, db)
    changes = payload.model_dump(exclude_unset=True)
    if "sku" in changes and changes["sku"] is not None:
        _ensure_unique_sku(changes["sku"], db, product_id=product.id)

    for field, value in changes.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    log_audit(
        db,
        user_id=current_user.id,
        action="UPDATE",
        entity="products",
        entity_id=product.id,
        details={"changed_fields": sorted(changes)},
    )
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "MANAGER")),
):
    product = _get_product_or_404(product_id, db)
    product_details = {"sku": product.sku, "name": product.name}
    db.delete(product)
    db.commit()
    log_audit(
        db,
        user_id=current_user.id,
        action="DELETE",
        entity="products",
        entity_id=product_id,
        details=product_details,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
