"""Run an end-to-end API-key check against the configured development database."""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException, Request

import app.models  # noqa: F401 - registers all SQLAlchemy models
from app.api.deps import get_current_api_key
from app.api.v1.endpoints.integration import (
    create_partner_product,
    delete_partner_product,
    list_partner_products,
    update_partner_product,
)
from app.db.session import SessionLocal
from app.models.api_key import ApiKey
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.models.user import User, UserRole
from app.services.api_keys import generate_api_key


def main() -> None:
    db = SessionLocal()
    temporary_key: ApiKey | None = None
    temporary_product_id: str | None = None
    try:
        admin = (
            db.query(User)
            .filter(User.role == UserRole.ADMIN, User.is_active.is_(True))
            .first()
        )
        if admin is None:
            raise RuntimeError("No active ADMIN account exists for the smoke test")

        raw_key, key_prefix, key_hash = generate_api_key()
        temporary_key = ApiKey(
            name="TEMPORARY API KEY SMOKE TEST",
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=[
                "products:read",
                "products:create",
                "products:update",
                "products:delete",
            ],
            created_by=admin.id,
        )
        db.add(temporary_key)
        db.commit()
        db.refresh(temporary_key)

        request = Request(
            {"type": "http", "headers": [], "client": ("127.0.0.1", 0)}
        )
        authenticated_key = get_current_api_key(request=request, raw_key=raw_key, db=db)
        products = list_partner_products(
            search=None,
            category_id=None,
            supplier_id=None,
            location_id=None,
            low_stock=None,
            skip=0,
            limit=5,
            db=db,
            _api_key=authenticated_key,
        )
        print(f"ACTIVE_KEY_AUTHENTICATED products_returned={len(products)}")

        sku = f"API-SMOKE-{uuid.uuid4().hex[:12].upper()}"
        product = create_partner_product(
            payload=ProductCreate(
                sku=sku,
                name="Temporary API smoke product",
                price="1.00",
            ),
            request=request,
            db=db,
            api_key=authenticated_key,
        )
        temporary_product_id = product.id
        print("PRODUCT_CREATE_OK")

        updated_product = update_partner_product(
            product_id=temporary_product_id,
            payload=ProductUpdate(name="Updated temporary API smoke product"),
            request=request,
            db=db,
            api_key=authenticated_key,
        )
        if updated_product.name != "Updated temporary API smoke product":
            raise RuntimeError("Partner product update did not persist")
        print("PRODUCT_UPDATE_OK")

        delete_partner_product(
            product_id=temporary_product_id,
            request=request,
            db=db,
            api_key=authenticated_key,
        )
        temporary_product_id = None
        print("PRODUCT_DELETE_OK")

        temporary_key.is_active = False
        db.commit()
        try:
            get_current_api_key(request=request, raw_key=raw_key, db=db)
        except HTTPException as exc:
            if exc.status_code != 401:
                raise
            print("REVOKED_KEY_REJECTED")
        else:
            raise RuntimeError("Revoked API key was unexpectedly accepted")
    finally:
        if temporary_product_id is not None:
            db.query(Product).filter(Product.id == temporary_product_id).delete()
            db.commit()
            print("TEMPORARY_PRODUCT_REMOVED")
        if temporary_key is not None:
            db.refresh(temporary_key)
            db.delete(temporary_key)
            db.commit()
            print("TEMPORARY_KEY_REMOVED")
        db.close()


if __name__ == "__main__":
    main()
