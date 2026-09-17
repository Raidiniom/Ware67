from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles
from app.models.product import Product
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.location import Location
from app.schemas.product import ProductCreate, ProductUpdate, ProductRead

router = APIRouter(prefix="/products", tags=["products"])


def _validate_refs(db: Session, category_id, supplier_id, location_id):
    if category_id and not db.query(Category).filter(Category.id == category_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="category_id does not exist")
    if supplier_id and not db.query(Supplier).filter(Supplier.id == supplier_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="supplier_id does not exist")
    if location_id and not db.query(Location).filter(Location.id == location_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="location_id does not exist")


@router.get("", response_model=list[ProductRead])
def list_products(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Product).order_by(Product.name).all()


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ADMIN", "MANAGER")),
):
    existing = db.query(Product).filter(Product.sku == payload.sku).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A product with this SKU already exists")

    _validate_refs(db, payload.category_id, payload.supplier_id, payload.location_id)

    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ADMIN", "MANAGER")),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    data = payload.model_dump(exclude_unset=True)

    if "sku" in data and data["sku"] != product.sku:
        clash = db.query(Product).filter(Product.sku == data["sku"]).first()
        if clash:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A product with this SKU already exists")

    _validate_refs(
        db,
        data.get("category_id", product.category_id),
        data.get("supplier_id", product.supplier_id),
        data.get("location_id", product.location_id),
    )

    for field, value in data.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ADMIN", "MANAGER")),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(product)
    db.commit()
    return None
