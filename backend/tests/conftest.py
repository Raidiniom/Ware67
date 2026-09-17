import os
from contextlib import contextmanager

# These must be set before anything under `app` is imported, because
# app.core.config.settings is instantiated at import time and
# app.db.session creates its SQLAlchemy engine at import time too.
os.environ.setdefault("DATABASE_URL", "sqlite:///./_unused_import_time.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base_class import Base
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserRole

# A single shared in-memory SQLite connection for the whole test run.
# StaticPool + check_same_thread=False lets FastAPI's TestClient (which
# runs endpoint code in a worker thread) share the same in-memory DB.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _make_user(db_session, role: UserRole, email: str) -> User:
    user = User(name=f"{role.value} user", email=email, password="hashed", role=role, is_active=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_user(db_session):
    return _make_user(db_session, UserRole.ADMIN, "admin@ware67.test")


@pytest.fixture()
def manager_user(db_session):
    return _make_user(db_session, UserRole.MANAGER, "manager@ware67.test")


@pytest.fixture()
def staff_user(db_session):
    return _make_user(db_session, UserRole.STAFF, "staff@ware67.test")


@pytest.fixture()
def admin_client(client, admin_user):
    """A TestClient that acts as an authenticated ADMIN, bypassing real JWTs."""
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def manager_client(client, manager_user):
    """A TestClient that acts as an authenticated MANAGER."""
    app.dependency_overrides[get_current_user] = lambda: manager_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def staff_client(client, staff_user):
    """A TestClient that acts as an authenticated STAFF user (read-only role)."""
    app.dependency_overrides[get_current_user] = lambda: staff_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def login_as(client):
    """
    For tests that need to act as more than one role against the SAME client
    within a single test (e.g. "create as admin, then try to delete as manager").

    admin_client / manager_client / staff_client all share one underlying
    TestClient and one dependency_overrides dict, so requesting two of them in
    the same test is a trap: whichever fixture is resolved last silently wins
    for BOTH names, and earlier calls in the test body run as the wrong user.
    `login_as` scopes the override to just the `with` block instead.

        def test_x(client, admin_user, staff_user, login_as):
            with login_as(admin_user):
                ...  # acts as admin
            with login_as(staff_user):
                ...  # acts as staff
    """

    @contextmanager
    def _login(user):
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    return _login
