import unittest

from app.api.v1.endpoints.api_keys import router as management_router
from app.api.v1.endpoints.integration import router as integration_router
from app.schemas.api_key import ApiKeyCreate
from app.services.api_keys import (
    extract_key_prefix,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)


class ApiKeyRequirementsTests(unittest.TestCase):
    def test_generated_key_can_be_verified_without_storing_raw_value(self):
        raw_key, prefix, stored_hash = generate_api_key()

        self.assertTrue(raw_key.startswith(prefix + "_"))
        self.assertEqual(extract_key_prefix(raw_key), prefix)
        self.assertEqual(len(stored_hash), 64)
        self.assertEqual(stored_hash, hash_api_key(raw_key))
        self.assertTrue(verify_api_key(raw_key, stored_hash))
        self.assertFalse(verify_api_key(raw_key + "changed", stored_hash))
        self.assertNotIn(raw_key, stored_hash)

    def test_invalid_key_format_has_no_prefix(self):
        self.assertIsNone(extract_key_prefix("not-a-ware67-key"))

    def test_management_and_partner_routes_are_registered(self):
        management_paths = {route.path for route in management_router.routes}
        integration_paths = {route.path for route in integration_router.routes}

        self.assertIn("/api-keys", management_paths)
        self.assertIn("/api-keys/{api_key_id}", management_paths)
        self.assertIn("/integration/products", integration_paths)
        self.assertIn("/integration/products/{product_id}", integration_paths)
        self.assertIn("/integration/categories", integration_paths)
        self.assertIn("/integration/suppliers", integration_paths)
        self.assertIn("/integration/locations", integration_paths)

        product_routes = [
            route for route in integration_router.routes
            if route.path in {"/integration/products", "/integration/products/{product_id}"}
        ]
        methods = {method for route in product_routes for method in route.methods}
        self.assertTrue({"GET", "POST", "PATCH", "DELETE"}.issubset(methods))

    def test_product_write_scopes_are_supported(self):
        payload = ApiKeyCreate(
            company_id="company-1",
            name="Full product integration",
            scopes=[
                "products:read",
                "products:create",
                "products:update",
                "products:delete",
            ],
        )

        self.assertEqual(
            payload.scopes,
            [
                "products:read",
                "products:create",
                "products:update",
                "products:delete",
            ],
        )

    def test_duplicate_scopes_are_removed(self):
        payload = ApiKeyCreate(
            company_id="company-1",
            name="Read integration",
            scopes=["products:read", "products:read"],
        )

        self.assertEqual(payload.scopes, ["products:read"])


if __name__ == "__main__":
    unittest.main()
