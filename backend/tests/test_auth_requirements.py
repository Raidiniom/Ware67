import unittest

from app.models.user import UserRole
from app.schemas.auth import RegisterRequest


class AuthRequirementsTests(unittest.TestCase):
    def test_guest_role_is_available(self):
        self.assertEqual(UserRole.GUEST.value, "GUEST")

    def test_register_requires_an_eight_character_password(self):
        with self.assertRaises(ValueError):
            RegisterRequest(name="Jane", email="jane@example.com", password="short")
