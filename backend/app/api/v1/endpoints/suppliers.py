from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_member, require_roles
from app.db.session import get_db
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.common import ProductBrief
from app.schemas.supplier import SupplierCreate, SupplierList, SupplierRead, SupplierUpdate
from app.services.audit import log_audit
from app.services.tenancy import get_owned_or_404

router = APIRouter(prefix="/suppliers", tags=["suppliers"])
writer = require_roles("ADMIN", "MANAGER")

FIELDS = ("name", "contact_person", "contact_number", "email", "address")


def _snapshot(s: Supplier) -> dict:
    return {f: getattr(s, f) for f in FIELDS}


def _to_read(s: Supplier, count: int) -> SupplierRead:
    r = SupplierRead.model_validate(s)
    r.product_count = count
    return r


def _get_or_404(db: Session, supplier_id: str, company_id: str) -> Supplier:
    return get_owned_or_404(db, Supplier, supplier_id, company_id, "Supplier")


def _count(db: Session, supplier_id: str, company_id: str) -> int:
    return (db.query(func.count(Product.id))
            .filter(Product.supplier_id == supplier_id, Product.company_id == company_id)
            .scalar())


@router.get("", response_model=SupplierList)
def list_suppliers(
    search: str | None = None,
    has_products: bool | None = None,
    has_email: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_member),
):
    count_col = func.count(Product.id).label("product_count")
    q = (db.query(Supplier, count_col)
         .outerjoin(Product, (Product.supplier_id == Supplier.id)
                    & (Product.company_id == user.company_id))
         .filter(Supplier.company_id == user.company_id)
         .group_by(Supplier.id))
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(or_(Supplier.name.like(like), Supplier.contact_person.like(like),
                         Supplier.email.like(like), Supplier.contact_number.like(like)))
    if has_email is True:
        q = q.filter(Supplier.email.isnot(None))
    elif has_email is False:
        q = q.filter(Supplier.email.is_(None))
    if has_products is True:
        q = q.having(count_col > 0)
    elif has_products is False:
        q = q.having(count_col == 0)

    total = q.count()
    rows = q.order_by(Supplier.name).offset(skip).limit(limit).all()
    return SupplierList(items=[_to_read(s, n) for s, n in rows], total=total)


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_member)):
    s = _get_or_404(db, supplier_id, user.company_id)
    return _to_read(s, _count(db, s.id, user.company_id))


@router.get("/{supplier_id}/products", response_model=list[ProductBrief])
def supplier_products(supplier_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_member)):
    _get_or_404(db, supplier_id, user.company_id)
    return (db.query(Product)
            .filter(Product.supplier_id == supplier_id, Product.company_id == user.company_id)
            .order_by(Product.name).all())


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    s = Supplier(**payload.model_dump(), company_id=user.company_id)
    db.add(s)
    db.flush()
    log_audit(db, user_id=user.id, action="CREATE", entity="SUPPLIER", entity_id=s.id,
              details={"new_value": _snapshot(s)}, request=request)
    db.commit()
    db.refresh(s)
    return _to_read(s, 0)


@router.put("/{supplier_id}", response_model=SupplierRead)
def update_supplier(supplier_id: str, payload: SupplierUpdate, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    s = _get_or_404(db, supplier_id, user.company_id)
    before = _snapshot(s)
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    log_audit(db, user_id=user.id, action="UPDATE", entity="SUPPLIER", entity_id=s.id,
              details={"previous_value": before, "new_value": _snapshot(s)}, request=request)
    db.commit()
    db.refresh(s)
    return _to_read(s, _count(db, s.id, user.company_id))


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(supplier_id: str, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    s = _get_or_404(db, supplier_id, user.company_id)
    log_audit(db, user_id=user.id, action="DELETE", entity="SUPPLIER", entity_id=s.id,
              details={"previous_value": _snapshot(s),
                       "products_unassigned": _count(db, s.id, user.company_id)},
              request=request)
    db.delete(s)  # ON DELETE SET NULL keeps the products
    db.commit()