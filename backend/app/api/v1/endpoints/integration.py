from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_api_key_scope
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.product import Product
from app.schemas.product import ProductRead

router = APIRouter(prefix="/integration", tags=["Partner integration"])
products_reader = require_api_key_scope("products:read")


@router.get("/products", response_model=list[ProductRead])
def list_partner_products(
    search: str | None = Query(default=None, max_length=200),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _api_key: ApiKey = Depends(products_reader),
):
    query = db.query(Product)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Product.sku.ilike(term), Product.name.ilike(term)))
    return query.order_by(Product.name.asc()).offset(skip).limit(limit).all()


@router.get("/products/{product_id}", response_model=ProductRead)
def get_partner_product(
    product_id: str,
    db: Session = Depends(get_db),
    _api_key: ApiKey = Depends(products_reader),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product
