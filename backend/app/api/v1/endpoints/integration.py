from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_api_key_scope
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.category import Category
from app.models.location import Location
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.transaction import Transaction
from app.schemas.category import CategoryRead
from app.schemas.location import LocationRead
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.schemas.supplier import SupplierRead
from app.services.audit import log_audit
from app.services.tenancy import ensure_product_refs, get_owned_or_404

router = APIRouter(prefix="/integration", tags=["Partner integration"])
products_reader = require_api_key_scope("products:read")
products_creator = require_api_key_scope("products:create")
products_updater = require_api_key_scope("products:update")
products_deleter = require_api_key_scope("products:delete")

# Every query here is limited to the key's own company (api_key.company_id).


def _get_product_or_404(product_id: str, db: Session, company_id: str) -> Product:
    return get_owned_or_404(db, Product, product_id, company_id, "Product")


def _ensure_unique_sku(sku: str, db: Session, company_id: str, product_id: str | None = None) -> None:
    query = db.query(Product).filter(Product.company_id == company_id, Product.sku == sku)
    if product_id is not None:
        query = query.filter(Product.id != product_id)
    if query.first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A product with this SKU already exists")


def _partner_audit(db: Session, api_key: ApiKey, request: Request, *, action: str, entity: str,
                   entity_id: str, details: dict) -> None:
    """Partner actions are recorded against the company and the key, not
    against a person: no user acted, an integration did."""
    log_audit(
        db,
        user_id=None,
        company_id=api_key.company_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details={**details, "api_key_id": api_key.id, "api_key_name": api_key.name},
        request=request,
    )


@router.get("/products", response_model=list[ProductRead])
def list_partner_products(
    search: str | None = Query(default=None, max_length=200),
    category_id: str | None = None,
    supplier_id: str | None = None,
    location_id: str | None = None,
    low_stock: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(products_reader),
):
    query = db.query(Product).filter(Product.company_id == api_key.company_id)
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


@router.get("/products/{product_id}", response_model=ProductRead)
def get_partner_product(
    product_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(products_reader),
):
    return _get_product_or_404(product_id, db, api_key.company_id)


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_partner_product(
    payload: ProductCreate,
    request: Request,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(products_creator),
):
    data = payload.model_dump()
    initial_stock = data.pop("initial_stock", 0) or 0
    data.pop("current_stock", None)
    company_id = api_key.company_id
    _ensure_unique_sku(data["sku"], db, company_id)
    ensure_product_refs(db, data, company_id)

    product = Product(**data, company_id=company_id, current_stock=initial_stock)
    db.add(product)
    db.flush()
    _partner_audit(db, api_key, request, action="CREATE", entity="PRODUCT", entity_id=product.id,
                   details={"sku": product.sku, "name": product.name})

    if initial_stock > 0:
        txn = Transaction(
            company_id=company_id,
            product_id=product.id,
            api_key_id=api_key.id,
            type="STOCK_IN",
            quantity=initial_stock,
            reference_type="INITIAL",
            notes=f"Opening stock via partner API key: {api_key.name}",
        )
        db.add(txn)
        db.flush()
        _partner_audit(
            db, api_key, request, action="STOCK_IN", entity="TRANSACTION", entity_id=txn.id,
            details={
                "product_id": product.id,
                "quantity": initial_stock,
                "previous_value": 0,
                "new_value": initial_stock,
                "reference_type": "INITIAL",
            },
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A product with this SKU already exists")
    db.refresh(product)
    return product


@router.patch("/products/{product_id}", response_model=ProductRead)
def update_partner_product(
    product_id: str,
    payload: ProductUpdate,
    request: Request,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(products_updater),
):
    company_id = api_key.company_id
    product = _get_product_or_404(product_id, db, company_id)
    changes = payload.model_dump(exclude_unset=True)

    for field in ("sku", "name", "price", "reorder_level"):
        if changes.get(field, "") is None:
            changes.pop(field)

    if changes.get("sku") is not None:
        _ensure_unique_sku(changes["sku"], db, company_id, product_id=product.id)
    ensure_product_refs(db, changes, company_id)

    before = {field: getattr(product, field) for field in changes}
    for field, value in changes.items():
        setattr(product, field, value)
    _partner_audit(
        db, api_key, request, action="UPDATE", entity="PRODUCT", entity_id=product.id,
        details=jsonable_encoder(
            {"changed_fields": sorted(changes), "previous_value": before, "new_value": changes}
        ),
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Product could not be updated")
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_partner_product(
    product_id: str,
    request: Request,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(products_deleter),
):
    product = _get_product_or_404(product_id, db, api_key.company_id)
    _partner_audit(db, api_key, request, action="DELETE", entity="PRODUCT", entity_id=product.id,
                   details={"sku": product.sku, "name": product.name})
    db.delete(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This product has transaction or adjustment history and can't be deleted.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/categories", response_model=list[CategoryRead])
def list_partner_categories(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(products_reader),
):
    return (db.query(Category).filter(Category.company_id == api_key.company_id)
            .order_by(Category.name.asc()).all())


@router.get("/suppliers", response_model=list[SupplierRead])
def list_partner_suppliers(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(products_reader),
):
    return (db.query(Supplier).filter(Supplier.company_id == api_key.company_id)
            .order_by(Supplier.name.asc()).all())


@router.get("/locations", response_model=list[LocationRead])
def list_partner_locations(
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(products_reader),
):
    return (db.query(Location).filter(Location.company_id == api_key.company_id)
            .order_by(Location.name.asc()).all())
