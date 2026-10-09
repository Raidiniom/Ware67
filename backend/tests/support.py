"""Shared setup for API-level tests: the real FastAPI app on an in-memory
SQLite database, plus helpers to create companies, users and API keys."""
import os
import unittest
from datetime import datetime, timedelta, timezone

# Only used when no backend/.env is present (e.g. running a file alone in CI).
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.api import deps
from app.core.security import create_access_token, hash_password
from app.db.base_class import Base
from app.db.session import get_db
from app.main import app
from app.models.api_key import ApiKey
from app.models.company import Company
from app.models.user import User, UserRole
from app.services.api_keys import generate_api_key

PASSWORD = "Original123"


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

        # The limiters are module-level, so counts would leak between tests.
        for limiter in (deps.api_key_limiter, deps.failed_attempt_limiter):
            limiter.reset()
            self.addCleanup(limiter.reset)

    # --- builders -------------------------------------------------------

    def add(self, obj):
        """Inserts one row and returns its id."""
        db = self.Session()
        try:
            db.add(obj)
            db.commit()
            return obj.id
        finally:
            db.close()

    def make_company(self, name="Acme", is_active=True) -> str:
        return self.add(Company(name=name, is_active=is_active))

    def make_user(self, company_id, role=UserRole.OWNER, *, email=None, is_active=True) -> str:
        email = email or f"{role.value.lower()}.{company_id[:8]}@example.com"
        return self.add(User(name=f"{role.value.title()} User", email=email,
                             password=hash_password(PASSWORD), role=role,
                             company_id=company_id, is_active=is_active))

    def make_platform_admin(self, email="platform@ware67.com") -> str:
        return self.add(User(name="Platform Admin", email=email, password=hash_password(PASSWORD),
                             role=UserRole.GUEST, company_id=None, is_platform_admin=True))

    def make_key(self, company_id, created_by, scopes=("products:read",), **fields):
        """Inserts a key directly and returns (raw_key, key_id)."""
        raw_key, prefix, key_hash = generate_api_key()
        key_id = self.add(ApiKey(
            company_id=company_id,
            name=fields.pop("name", "Test partner"),
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=list(scopes),
            created_by=created_by,
            expires_at=fields.pop("expires_at", utcnow() + timedelta(days=30)),
            **fields,
        ))
        return raw_key, key_id

    # --- helpers --------------------------------------------------------

    def auth(self, user_id):
        db = self.Session()
        try:
            user = db.get(User, user_id)
            return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}
        finally:
            db.close()

    def get(self, model, obj_id):
        db = self.Session()
        try:
            return db.get(model, obj_id)
        finally:
            db.close()
