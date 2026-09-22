import unittest
from decimal import Decimal

from pydantic import ValidationError

from app.api.v1.endpoints.products import router
from app.schemas.product import ProductCreate, ProductUpdate


class ProductRequirementsTests(unittest.TestCase):
    def test_product_routes_are_registered(self):
        routes = {(route.path, frozenset(route.methods or [])) for route in router.routes}

        self.assertIn(("/products", frozenset({"GET"})), routes)
        self.assertIn(("/products", frozenset({"POST"})), routes)
        self.assertIn(("/products/{product_id}", frozenset({"GET"})), routes)
        self.assertIn(("/products/{product_id}", frozenset({"PATCH"})), routes)
        self.assertIn(("/products/{product_id}", frozenset({"DELETE"})), routes)

    def test_product_create_trims_text_and_applies_defaults(self):
        payload = ProductCreate(sku="  SKU-001  ", name="  Sample product  ")

        self.assertEqual(payload.sku, "SKU-001")
        self.assertEqual(payload.name, "Sample product")
        self.assertEqual(payload.price, Decimal("0.00"))
        self.assertEqual(payload.reorder_level, 0)

    def test_product_create_rejects_invalid_values(self):
        invalid_fields = [
            ("sku", "   "),
            ("name", "   "),
            ("price", "-1.00"),
            ("reorder_level", -1),
        ]

        for field, value in invalid_fields:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ProductCreate(**{"sku": "SKU-001", "name": "Sample product", field: value})

    def test_product_update_only_contains_supplied_fields(self):
        payload = ProductUpdate(name="Updated name")

        self.assertEqual(payload.model_dump(exclude_unset=True), {"name": "Updated name"})


if __name__ == "__main__":
    unittest.main()
