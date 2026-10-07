"""Run an end-to-end API-key check against the configured development database."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

import app.models  # noqa: F401 - registers all SQLAlchemy models
from app.api.deps import get_current_api_key
from app.api.v1.endpoints.integration import list_partner_products
from app.db.session import SessionLocal
from app.models.api_key import ApiKey
from app.models.user import User, UserRole
from app.services.api_keys import generate_api_key


def main() -> None:
    db = SessionLocal()
    temporary_key: ApiKey | None = None
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
            scopes=["products:read"],
            created_by=admin.id,
        )
        db.add(temporary_key)
        db.commit()
        db.refresh(temporary_key)

        authenticated_key = get_current_api_key(raw_key=raw_key, db=db)
        products = list_partner_products(
            search=None,
            skip=0,
            limit=5,
            db=db,
            _api_key=authenticated_key,
        )
        print(f"ACTIVE_KEY_AUTHENTICATED products_returned={len(products)}")

        temporary_key.is_active = False
        db.commit()
        try:
            get_current_api_key(raw_key=raw_key, db=db)
        except HTTPException as exc:
            if exc.status_code != 401:
                raise
            print("REVOKED_KEY_REJECTED")
        else:
            raise RuntimeError("Revoked API key was unexpectedly accepted")
    finally:
        if temporary_key is not None:
            db.delete(temporary_key)
            db.commit()
            print("TEMPORARY_KEY_REMOVED")
        db.close()


if __name__ == "__main__":
    main()
