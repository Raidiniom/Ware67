"""Company-scoped lookups. Every read of company data by id goes through
here, so another company's row looks exactly like a row that doesn't exist."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.location import Location
from app.models.supplier import Supplier


def get_owned_or_404(db: Session, model, obj_id: str, company_id: str, label: str):
    """The row with this id belonging to this company. 404 (never 403) for
    other companies' rows, so ids can't be probed for existence."""
    obj = db.query(model).filter(model.id == obj_id, model.company_id == company_id).first()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found")
    return obj


PRODUCT_REFS = (
    ("category_id", Category, "Category"),
    ("supplier_id", Supplier, "Supplier"),
    ("location_id", Location, "Location"),
)


def ensure_product_refs(db: Session, data: dict, company_id: str) -> None:
    """A product may only point at its own company's category, supplier and
    location."""
    for field, model, label in PRODUCT_REFS:
        ref = data.get(field)
        if ref is None:
            continue
        exists = db.query(model.id).filter(model.id == ref, model.company_id == company_id).first()
        if exists is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} not found")
