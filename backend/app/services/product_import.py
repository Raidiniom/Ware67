"""Bulk product import from a CSV file. All or nothing: every row is checked
first, and nothing is saved unless the whole file is valid, so a failed import
never leaves a half-loaded catalogue behind."""
import csv
import io
import uuid
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.location import Location
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.transaction import Transaction
from app.schemas.product import ProductCreate
from app.services.audit import log_audit
from app.services.csv_files import unescape_cell

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000

REQUIRED_COLUMNS = {"sku", "name"}
PRODUCT_COLUMNS = ("sku", "name", "description", "unit", "price", "reorder_level", "initial_stock")
# So a file from the products export can be imported into another company.
COLUMN_ALIASES = {"current_stock": "initial_stock"}
# column, model, id field on the product, audit entity
REFERENCES = (
    ("category", Category, "category_id", "CATEGORY"),
    ("supplier", Supplier, "supplier_id", "SUPPLIER"),
    ("location", Location, "location_id", "LOCATION"),
)
REFERENCE_NAME_MAX = 150


@dataclass
class ImportPlan:
    products: list[tuple[ProductCreate, dict[str, str]]] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    # column -> {lowercase name: existing id, or None if it would be created}
    references: dict[str, dict[str, str | None]] = field(default_factory=dict)
    # column -> {lowercase name: the name as first written in the file}
    new_names: dict[str, dict[str, str]] = field(default_factory=dict)


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel's plain "CSV" option saves in the Windows code page.
        return content.decode("cp1252", errors="replace")


def _read_rows(content: bytes) -> list[tuple[int, dict[str, str]]]:
    """Returns (spreadsheet row number, {column: value}) for each non-blank row."""
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is too large (2 MB at most)")

    reader = csv.reader(io.StringIO(_decode(content), newline=""))
    try:
        header = [cell.strip().lower() for cell in next(reader, [])]
        header = [COLUMN_ALIASES.get(name, name) for name in header]
        missing = REQUIRED_COLUMNS - set(header)
        if missing:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"The file needs these columns: {', '.join(sorted(missing))}")

        rows = []
        for cells in reader:
            values = [unescape_cell(cell.strip()) for cell in cells]
            if not any(values):
                continue
            if len(rows) == MAX_ROWS:
                raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                    f"The file has too many rows ({MAX_ROWS} at most)")
            rows.append((reader.line_num, dict(zip(header, values))))
    except csv.Error as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This doesn't look like a valid CSV file") from error

    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file has no product rows")
    return rows


def _validate(row: dict[str, str]) -> ProductCreate:
    # Blank cells fall back to the schema's defaults.
    data = {column: row[column] for column in PRODUCT_COLUMNS if row.get(column)}
    if "price" in data:
        data["price"] = data["price"].replace(",", "")  # spreadsheets write 1,200.50
    return ProductCreate(**data)


def plan_import(db: Session, content: bytes, company_id: str) -> ImportPlan:
    rows = _read_rows(content)
    plan = ImportPlan()
    for column, model, _, _ in REFERENCES:
        existing = db.query(model.name, model.id).filter(model.company_id == company_id).all()
        plan.references[column] = {name.lower(): ref_id for name, ref_id in existing}
        plan.new_names[column] = {}

    # Compared in lowercase, because MySQL's collation treats SKUs that way.
    seen_skus = {sku.lower() for sku, in db.query(Product.sku).filter(Product.company_id == company_id)}
    for line, row in rows:
        try:
            product = _validate(row)
        except ValidationError as error:
            plan.errors.extend(
                {"row": line, "field": str(e["loc"][0]) if e["loc"] else None,
                 "message": e["msg"].removeprefix("Value error, ")}
                for e in error.errors()
            )
            continue

        if product.sku.lower() in seen_skus:
            plan.errors.append({"row": line, "field": "sku",
                                "message": f"SKU {product.sku} already exists"})
            continue
        seen_skus.add(product.sku.lower())

        names = {}
        for column, _, _, _ in REFERENCES:
            name = row.get(column)
            if not name:
                continue
            if len(name) > REFERENCE_NAME_MAX:
                plan.errors.append({"row": line, "field": column,
                                    "message": f"must be at most {REFERENCE_NAME_MAX} characters"})
                continue
            names[column] = name
            if name.lower() not in plan.references[column]:
                plan.new_names[column].setdefault(name.lower(), name)
        plan.products.append((product, names))
    return plan


def apply_import(db: Session, plan: ImportPlan, user_id: str, company_id: str, request: Request) -> None:
    """Adds everything to the session. The caller commits. Ids are set here
    rather than by a flush per row, so large files insert in one batch."""
    reference_ids = {column: dict(known) for column, known in plan.references.items()}
    for column, model, _, entity in REFERENCES:
        for key, name in plan.new_names[column].items():
            ref_id = str(uuid.uuid4())
            db.add(model(id=ref_id, company_id=company_id, name=name))
            reference_ids[column][key] = ref_id
            log_audit(db, user_id=user_id, company_id=company_id, action="CREATE", entity=entity,
                      entity_id=ref_id, details={"new_value": {"name": name}, "via": "csv_import"},
                      request=request)

    for payload, names in plan.products:
        data = payload.model_dump()
        initial_stock = data.pop("initial_stock")
        for column, _, id_field, _ in REFERENCES:
            if column in names:
                data[id_field] = reference_ids[column][names[column].lower()]

        product_id = str(uuid.uuid4())
        db.add(Product(id=product_id, company_id=company_id, current_stock=initial_stock, **data))
        log_audit(db, user_id=user_id, company_id=company_id, action="CREATE", entity="PRODUCT",
                  entity_id=product_id, details={"sku": payload.sku, "name": payload.name, "via": "csv_import"},
                  request=request)

        if initial_stock > 0:  # opening stock gets a history row, like a single create
            txn_id = str(uuid.uuid4())
            db.add(Transaction(id=txn_id, company_id=company_id, product_id=product_id, user_id=user_id,
                               type="STOCK_IN", quantity=initial_stock, reference_type="INITIAL",
                               notes="Opening stock (CSV import)"))
            log_audit(db, user_id=user_id, company_id=company_id, action="STOCK_IN", entity="TRANSACTION",
                      entity_id=txn_id,
                      details={"product_id": product_id, "quantity": initial_stock, "previous_value": 0,
                               "new_value": initial_stock, "reference_type": "INITIAL"},
                      request=request)
