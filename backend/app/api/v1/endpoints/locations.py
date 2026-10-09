from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_member, require_roles
from app.db.session import get_db
from app.models.location import Location
from app.models.product import Product
from app.models.user import User
from app.schemas.common import ProductBrief
from app.schemas.location import LocationCreate, LocationList, LocationRead, LocationUpdate
from app.services.audit import log_audit
from app.services.tenancy import get_owned_or_404

router = APIRouter(prefix="/locations", tags=["locations"])
writer = require_roles("ADMIN", "MANAGER")

FIELDS = ("name", "description", "warehouse", "aisle", "shelf", "bin")


def _snapshot(loc: Location) -> dict:
    return {f: getattr(loc, f) for f in FIELDS}


def _to_read(loc: Location, count: int) -> LocationRead:
    r = LocationRead.model_validate(loc)
    r.product_count = count
    return r


def _get_or_404(db: Session, location_id: str, company_id: str) -> Location:
    return get_owned_or_404(db, Location, location_id, company_id, "Location")


def _count(db: Session, location_id: str, company_id: str) -> int:
    return (db.query(func.count(Product.id))
            .filter(Product.location_id == location_id, Product.company_id == company_id)
            .scalar())


@router.get("", response_model=LocationList)
def list_locations(
    search: str | None = None,
    warehouse: str | None = None,
    aisle: str | None = None,
    shelf: str | None = None,
    has_products: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_member),
):
    count_col = func.count(Product.id).label("product_count")
    q = (db.query(Location, count_col)
         .outerjoin(Product, (Product.location_id == Location.id)
                    & (Product.company_id == user.company_id))
         .filter(Location.company_id == user.company_id)
         .group_by(Location.id))
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(or_(Location.name.like(like), Location.description.like(like),
                         Location.warehouse.like(like), Location.aisle.like(like),
                         Location.shelf.like(like), Location.bin.like(like)))
    if warehouse:
        q = q.filter(Location.warehouse == warehouse)
    if aisle:
        q = q.filter(Location.aisle == aisle)
    if shelf:
        q = q.filter(Location.shelf == shelf)
    if has_products is True:
        q = q.having(count_col > 0)
    elif has_products is False:
        q = q.having(count_col == 0)

    total = q.count()
    rows = (q.order_by(Location.warehouse, Location.aisle, Location.shelf, Location.bin, Location.name)
            .offset(skip).limit(limit).all())
    return LocationList(items=[_to_read(loc, n) for loc, n in rows], total=total)


# Declared before "/{location_id}" so "warehouses" isn't treated as an id.
@router.get("/warehouses", response_model=list[str])
def list_warehouses(db: Session = Depends(get_db), user: User = Depends(get_current_member)):
    rows = (db.query(Location.warehouse)
            .filter(Location.company_id == user.company_id, Location.warehouse.isnot(None))
            .distinct().order_by(Location.warehouse).all())
    return [r[0] for r in rows]


@router.get("/{location_id}", response_model=LocationRead)
def get_location(location_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_member)):
    loc = _get_or_404(db, location_id, user.company_id)
    return _to_read(loc, _count(db, loc.id, user.company_id))


@router.get("/{location_id}/products", response_model=list[ProductBrief])
def location_products(location_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_member)):
    _get_or_404(db, location_id, user.company_id)
    return (db.query(Product)
            .filter(Product.location_id == location_id, Product.company_id == user.company_id)
            .order_by(Product.name).all())


@router.post("", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
def create_location(payload: LocationCreate, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    loc = Location(**payload.model_dump(), company_id=user.company_id)
    db.add(loc)
    db.flush()
    log_audit(db, user_id=user.id, action="CREATE", entity="LOCATION", entity_id=loc.id,
              details={"new_value": _snapshot(loc)}, request=request)
    db.commit()
    db.refresh(loc)
    return _to_read(loc, 0)


@router.put("/{location_id}", response_model=LocationRead)
def update_location(location_id: str, payload: LocationUpdate, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    loc = _get_or_404(db, location_id, user.company_id)
    before = _snapshot(loc)
    for k, v in payload.model_dump().items():
        setattr(loc, k, v)
    log_audit(db, user_id=user.id, action="UPDATE", entity="LOCATION", entity_id=loc.id,
              details={"previous_value": before, "new_value": _snapshot(loc)}, request=request)
    db.commit()
    db.refresh(loc)
    return _to_read(loc, _count(db, loc.id, user.company_id))


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(location_id: str, request: Request,
                    db: Session = Depends(get_db), user: User = Depends(writer)):
    loc = _get_or_404(db, location_id, user.company_id)
    log_audit(db, user_id=user.id, action="DELETE", entity="LOCATION", entity_id=loc.id,
              details={"previous_value": _snapshot(loc),
                       "products_unassigned": _count(db, loc.id, user.company_id)},
              request=request)
    db.delete(loc)
    db.commit()