from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.schemas.category import (CategoryCreate, CategoryList, CategoryProduct,
                                  CategoryRead, CategoryUpdate)
from app.services.audit import log_action

router = APIRouter(prefix="/categories", tags=["categories"])
writer = require_roles("ADMIN", "MANAGER")


def _to_read(cat: Category, count: int) -> CategoryRead:
    r = CategoryRead.model_validate(cat)
    r.product_count = count
    return r


def _get_or_404(db: Session, category_id: str) -> Category:
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return cat


def _ensure_unique(db: Session, name: str, exclude_id: str | None = None):
    q = db.query(Category.id).filter(func.lower(Category.name) == name.lower())
    if exclude_id:
        q = q.filter(Category.id != exclude_id)
    if q.first():
        raise HTTPException(status.HTTP_409_CONFLICT, "A category with this name already exists")


@router.get("", response_model=CategoryList)
def list_categories(
    search: str | None = None,
    has_products: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    count_col = func.count(Product.id).label("product_count")
    q = (db.query(Category, count_col)
         .outerjoin(Product, Product.category_id == Category.id)
         .group_by(Category.id))
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(Category.name.like(like) | Category.description.like(like))
    if has_products is True:
        q = q.having(count_col > 0)
    elif has_products is False:
        q = q.having(count_col == 0)

    total = q.count()
    rows = q.order_by(Category.name).offset(skip).limit(limit).all()
    return CategoryList(items=[_to_read(c, n) for c, n in rows], total=total)


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(category_id: str, db: Session = Depends(get_db),
                 _: User = Depends(get_current_user)):
    cat = _get_or_404(db, category_id)
    n = db.query(func.count(Product.id)).filter(Product.category_id == cat.id).scalar()
    return _to_read(cat, n)


@router.get("/{category_id}/products", response_model=list[CategoryProduct])
def category_products(category_id: str, db: Session = Depends(get_db),
                      _: User = Depends(get_current_user)):
    _get_or_404(db, category_id)
    return db.query(Product).filter(Product.category_id == category_id).order_by(Product.name).all()


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    _ensure_unique(db, payload.name)
    cat = Category(name=payload.name, description=payload.description)
    db.add(cat)
    db.flush()  # populate cat.id
    log_action(db, user_id=user.id, action="CREATE", entity="CATEGORY", entity_id=cat.id,
               details={"new_value": {"name": cat.name, "description": cat.description}},
               request=request)
    db.commit()
    db.refresh(cat)
    return _to_read(cat, 0)


@router.put("/{category_id}", response_model=CategoryRead)
def update_category(category_id: str, payload: CategoryUpdate, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    cat = _get_or_404(db, category_id)
    _ensure_unique(db, payload.name, exclude_id=cat.id)
    before = {"name": cat.name, "description": cat.description}
    cat.name, cat.description = payload.name, payload.description
    log_action(db, user_id=user.id, action="UPDATE", entity="CATEGORY", entity_id=cat.id,
               details={"previous_value": before,
                        "new_value": {"name": cat.name, "description": cat.description}},
               request=request)
    db.commit()
    db.refresh(cat)
    n = db.query(func.count(Product.id)).filter(Product.category_id == cat.id).scalar()
    return _to_read(cat, n)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: str, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    cat = _get_or_404(db, category_id)
    affected = db.query(func.count(Product.id)).filter(Product.category_id == cat.id).scalar()
    log_action(db, user_id=user.id, action="DELETE", entity="CATEGORY", entity_id=cat.id,
               details={"previous_value": {"name": cat.name, "description": cat.description},
                        "products_unassigned": affected},
               request=request)
    db.delete(cat)  # DB-level ON DELETE SET NULL clears products.category_id
    db.commit()