"""API-level regression tests for the authorization fixes.

Runs the real FastAPI app against an in-memory SQLite database, so no
tunnel or shared MySQL is needed:  python -m unittest discover -s tests
"""
import os
import unittest

# Only used when no backend/.env is present (e.g. running this file alone in CI).
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.base_class import Base
from app.db.session import get_db
from app.main import app
from app.models.product import Product
from app.models.user import User, UserRole


class SecurityFixTests(unittest.TestCase):
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

        db = self.Session()
        self.users = {}
        for role in UserRole:
            user = User(
                name=f"{role.value.title()} User",
                email=f"{role.value.lower()}@example.com",
                password=hash_password("Original123"),
                role=role,
            )
            db.add(user)
            db.flush()
            self.users[role] = user.id
        product = Product(sku="SKU-1", name="Widget", current_stock=10)
        db.add(product)
        db.commit()
        self.product_id = product.id
        db.close()

    def auth(self, role):
        return {"Authorization": f"Bearer {create_access_token(self.users[role], role.value)}"}

    def user(self, role):
        db = self.Session()
        try:
            return db.get(User, self.users[role])
        finally:
            db.close()

    def stock(self):
        db = self.Session()
        try:
            return db.get(Product, self.product_id).current_stock
        finally:
            db.close()

    # 1. Unauthenticated password reset is gone
    def test_forgot_password_cannot_take_over_an_account(self):
        response = self.client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "admin@example.com", "new_password": "Hijacked123"},
        )
        self.assertIn(response.status_code, (404, 405))
        self.assertTrue(verify_password("Original123", self.user(UserRole.ADMIN).password))

    # 2. Managers cannot escalate or touch privileged accounts via /auth routes
    def test_manager_cannot_onboard_themselves_as_admin(self):
        response = self.client.post(
            "/api/v1/auth/onboard",
            json={"user_id": self.users[UserRole.MANAGER], "role": "ADMIN", "is_active": True},
            headers=self.auth(UserRole.MANAGER),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.user(UserRole.MANAGER).role, UserRole.MANAGER)

    def test_manager_cannot_deactivate_an_admin(self):
        response = self.client.patch(
            "/api/v1/auth/update-status",
            json={"user_id": self.users[UserRole.ADMIN], "is_active": False},
            headers=self.auth(UserRole.MANAGER),
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.user(UserRole.ADMIN).is_active)

    def test_manager_can_still_onboard_a_guest_as_staff(self):
        response = self.client.post(
            "/api/v1/auth/onboard",
            json={"user_id": self.users[UserRole.GUEST], "role": "STAFF", "is_active": True},
            headers=self.auth(UserRole.MANAGER),
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.user(UserRole.GUEST).role, UserRole.STAFF)

    def test_admin_cannot_demote_themselves_via_update_role(self):
        response = self.client.patch(
            "/api/v1/auth/update-role",
            json={"user_id": self.users[UserRole.ADMIN], "role": "STAFF"},
            headers=self.auth(UserRole.ADMIN),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.user(UserRole.ADMIN).role, UserRole.ADMIN)

    def test_users_route_still_blocks_manager_editing_admin(self):
        response = self.client.patch(
            f"/api/v1/users/{self.users[UserRole.ADMIN]}",
            json={"is_active": False},
            headers=self.auth(UserRole.MANAGER),
        )
        self.assertEqual(response.status_code, 403)

    # 3. Guests cannot move stock
    def test_guest_cannot_record_a_transaction(self):
        response = self.client.post(
            "/api/v1/transactions",
            json={"product_id": self.product_id, "type": "STOCK_OUT", "quantity": 10},
            headers=self.auth(UserRole.GUEST),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.stock(), 10)

    def test_staff_can_record_a_transaction(self):
        response = self.client.post(
            "/api/v1/transactions",
            json={"product_id": self.product_id, "type": "STOCK_OUT", "quantity": 4},
            headers=self.auth(UserRole.STAFF),
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.stock(), 6)

    # 4. The app refuses to run with an empty signing secret
    def test_empty_jwt_secret_is_rejected(self):
        for secret in ("", "   "):
            with self.assertRaises(ValidationError):
                Settings(JWT_SECRET_KEY=secret, _env_file=None)


if __name__ == "__main__":
    unittest.main()
