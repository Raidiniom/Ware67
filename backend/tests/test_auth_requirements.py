from app.models.user import UserRole
from app.schemas.auth import ForgotPasswordRequest


def test_guest_role_is_available():
    assert UserRole.GUEST.value == "GUEST"


def test_forgot_password_accepts_email_and_new_password_only():
    payload = ForgotPasswordRequest(email="user@example.com", new_password="NewPass123")
    assert payload.email == "user@example.com"
    assert payload.new_password == "NewPass123"
