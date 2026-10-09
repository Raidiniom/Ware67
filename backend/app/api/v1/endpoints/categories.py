from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_member, require_roles
from app.db.session import get_db
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.schemas.category import (CategoryCreate, CategoryList, CategoryProduct,
                                  CategoryRead, CategoryUpdate)
from app.services.audit import log_action
from app.services.tenancy import get_owned_or_404

router = APIRouter(prefix="/categories", tags=["categories"])
writer = require_roles("ADMIN", "MANAGER")


def _to_read(cat: Category, count: int) -> CategoryRead:
    r = CategoryRead.model_validate(cat)
    r.product_count = count
    return r


def _get_or_404(db: Session, category_id: str, company_id: str) -> Category:
    return get_owned_or_404(db, Category, category_id, company_id, "Category")


def _count(db: Session, category_id: str, company_id: str) -> int:
    return (db.query(func.count(Product.id))
            .filter(Product.category_id == category_id, Product.company_id == company_id)
            .scalar())


def _ensure_unique(db: Session, name: str, company_id: str, exclude_id: str | None = None):
    q = db.query(Category.id).filter(Category.company_id == company_id,
                                     func.lower(Category.name) == name.lower())
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
    user: User = Depends(get_current_member),
):
    count_col = func.count(Product.id).label("product_count")
    q = (db.query(Category, count_col)
         .outerjoin(Product, (Product.category_id == Category.id)
                    & (Product.company_id == user.company_id))
         .filter(Category.company_id == user.company_id)
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
                 user: User = Depends(get_current_member)):
    cat = _get_or_404(db, category_id, user.company_id)
    return _to_read(cat, _count(db, cat.id, user.company_id))


@router.get("/{category_id}/products", response_model=list[CategoryProduct])
def category_products(category_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_member)):
    _get_or_404(db, category_id, user.company_id)
    return (db.query(Product)
            .filter(Product.category_id == category_id, Product.company_id == user.company_id)
            .order_by(Product.name).all())


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    _ensure_unique(db, payload.name, user.company_id)
    cat = Category(company_id=user.company_id, name=payload.name, description=payload.description)
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
    cat = _get_or_404(db, category_id, user.company_id)
    _ensure_unique(db, payload.name, user.company_id, exclude_id=cat.id)
    before = {"name": cat.name, "description": cat.description}
    cat.name, cat.description = payload.name, payload.description
    log_action(db, user_id=user.id, action="UPDATE", entity="CATEGORY", entity_id=cat.id,
               details={"previous_value": before,
                        "new_value": {"name": cat.name, "description": cat.description}},
               request=request)
    db.commit()
    db.refresh(cat)
    return _to_read(cat, _count(db, cat.id, user.company_id))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: str, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    cat = _get_or_404(db, category_id, user.company_id)
    affected = _count(db, cat.id, user.company_id)
    log_action(db, user_id=user.id, action="DELETE", entity="CATEGORY", entity_id=cat.id,
               details={"previous_value": {"name": cat.name, "description": cat.description},
                        "products_unassigned": affected},
               request=request)
    db.delete(cat)  # DB-level ON DELETE SET NULL clears products.category_id
    db.commit()