"""Changing your own password, the dashboard summary, and CSV import/export."""
import csv
import io
import unittest

from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.user import User, UserRole
from app.services.product_import import MAX_ROWS
from support import PASSWORD, ApiTestCase

API = "/api/v1"
HEADER = "sku,name,description,category,supplier,location,unit,price,reorder_level,initial_stock\n"


class BasicsTestCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.a = self.make_company("Company A")
        self.owner = self.make_user(self.a, UserRole.OWNER)
        self.manager = self.make_user(self.a, UserRole.MANAGER)
        self.staff = self.make_user(self.a, UserRole.STAFF)
        self.guest = self.make_user(self.a, UserRole.GUEST)
        self.b = self.make_company("Company B")
        self.b_owner = self.make_user(self.b, UserRole.OWNER)

    def count(self, model, **filters):
        db = self.Session()
        try:
            return db.query(model).filter_by(**filters).count()
        finally:
            db.close()


class ChangePasswordTests(BasicsTestCase):
    def change(self, user_id, current, new):
        return self.client.post(f"{API}/auth/change-password", headers=self.auth(user_id),
                                json={"current_password": current, "new_password": new})

    def login(self, user_id, password):
        email = self.get(User, user_id).email
        return self.client.post(f"{API}/auth/login", json={"email": email, "password": password})

    def test_every_role_can_change_their_own_password(self):
        for user_id in (self.owner, self.manager, self.staff, self.guest, self.make_platform_admin()):
            with self.subTest(user=user_id):
                self.assertEqual(self.change(user_id, PASSWORD, "BrandNew123").status_code, 204)
                self.assertEqual(self.login(user_id, "BrandNew123").status_code, 200)
                self.assertEqual(self.login(user_id, PASSWORD).status_code, 401)

    def test_wrong_current_password_changes_nothing(self):
        response = self.change(self.staff, "not-my-password", "BrandNew123")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.login(self.staff, PASSWORD).status_code, 200)

    def test_new_password_must_be_valid_and_different(self):
        self.assertEqual(self.change(self.staff, PASSWORD, "short").status_code, 422)
        self.assertEqual(self.change(self.staff, PASSWORD, PASSWORD).status_code, 400)

    def test_requires_sign_in(self):
        response = self.client.post(f"{API}/auth/change-password",
                                    json={"current_password": PASSWORD, "new_password": "BrandNew123"})
        self.assertEqual(response.status_code, 401)

    def test_change_is_audited_without_the_password(self):
        self.change(self.staff, PASSWORD, "BrandNew123")
        db = self.Session()
        try:
            row = db.query(AuditLog).filter_by(action="CHANGE_PASSWORD", user_id=self.staff).one()
            self.assertEqual(row.company_id, self.a)
            self.assertNotIn("BrandNew123", str(row.details))
        finally:
            db.close()


class DashboardSummaryTests(BasicsTestCase):
    def summary(self, user_id):
        return self.client.get(f"{API}/dashboard/summary", headers=self.auth(user_id))

    def test_empty_company(self):
        body = self.summary(self.owner).json()
        self.assertEqual(body["product_count"], 0)
        self.assertEqual(float(body["stock_value"]), 0)
        self.assertEqual(body["low_stock_items"], [])
        self.assertEqual(body["recent_movements"], [])

    def test_totals_and_low_stock(self):
        ok = self.add(Product(company_id=self.a, sku="OK", name="Plenty", price=2, current_stock=10, reorder_level=5))
        self.add(Product(company_id=self.a, sku="LOW", name="Running out", price=10, current_stock=3, reorder_level=5))
        self.add(Product(company_id=self.a, sku="OUT", name="Gone", price=99, current_stock=0, reorder_level=1))

        body = self.summary(self.guest).json()
        self.assertEqual(body["product_count"], 3)
        self.assertEqual(body["units_in_stock"], 13)
        self.assertEqual(body["low_stock_count"], 2)
        self.assertEqual(body["out_of_stock_count"], 1)
        self.assertEqual(float(body["stock_value"]), 50.0)
        self.assertEqual([item["sku"] for item in body["low_stock_items"]], ["OUT", "LOW"])
        self.assertNotIn(ok, [item["id"] for item in body["low_stock_items"]])

    def test_recent_movements_are_signed_and_named(self):
        product = self.add(Product(company_id=self.a, sku="P", name="Widget", current_stock=4))
        self.add(Transaction(company_id=self.a, product_id=product, user_id=self.staff, type="STOCK_OUT", quantity=3))
        self.add(InventoryAdjustment(company_id=self.a, product_id=product, user_id=self.owner,
                                     quantity_change=2, reason="Recount"))

        moves = {m["kind"]: m for m in self.summary(self.owner).json()["recent_movements"]}
        self.assertEqual(moves["TRANSACTION"]["quantity_change"], -3)
        self.assertEqual(moves["TRANSACTION"]["label"], "Stock out")
        self.assertEqual(moves["ADJUSTMENT"]["quantity_change"], 2)
        self.assertEqual(moves["ADJUSTMENT"]["label"], "Recount")

    def test_only_counts_the_callers_company(self):
        product = self.add(Product(company_id=self.a, sku="A", name="A's", price=5, current_stock=0, reorder_level=9))
        self.add(Transaction(company_id=self.a, product_id=product, user_id=self.owner, type="STOCK_IN", quantity=1))

        body = self.summary(self.b_owner).json()
        self.assertEqual(body["product_count"], 0)
        self.assertEqual(body["low_stock_items"], [])
        self.assertEqual(body["recent_movements"], [])

    def test_platform_admins_are_refused(self):
        self.assertEqual(self.summary(self.make_platform_admin()).status_code, 403)


class ExportTests(BasicsTestCase):
    def export(self, path, user_id, **params):
        response = self.client.get(f"{API}{path}", headers=self.auth(user_id), params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))

    def test_products_with_reference_names(self):
        category = self.add(Category(company_id=self.a, name="Hardware"))
        self.add(Product(company_id=self.a, sku="P1", name="Bolt", category_id=category, price=1.5, current_stock=7))

        rows = self.export("/products/export", self.guest)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "Hardware")
        self.assertEqual(rows[0]["current_stock"], "7")

    def test_products_respects_filters(self):
        self.add(Product(company_id=self.a, sku="P1", name="Bolt", current_stock=9, reorder_level=1))
        self.add(Product(company_id=self.a, sku="P2", name="Nut", current_stock=0, reorder_level=1))

        self.assertEqual([r["sku"] for r in self.export("/products/export", self.owner, low_stock="true")], ["P2"])
        self.assertEqual([r["sku"] for r in self.export("/products/export", self.owner, search="bolt")], ["P1"])

    def test_export_is_not_cut_off_at_the_list_limit(self):
        for i in range(201):
            self.add(Product(company_id=self.a, sku=f"S{i}", name=f"Item {i}"))
        self.assertEqual(len(self.export("/products/export", self.owner)), 201)

    def test_stock_history(self):
        product = self.add(Product(company_id=self.a, sku="P1", name="Bolt", current_stock=5))
        self.add(Transaction(company_id=self.a, product_id=product, user_id=self.staff, type="STOCK_IN",
                             quantity=5, reference_type="PO", reference_id="PO-1"))
        self.add(InventoryAdjustment(company_id=self.a, product_id=product, user_id=self.owner,
                                     quantity_change=-1, reason="Damaged"))

        txn = self.export("/transactions/export", self.guest)[0]
        self.assertEqual((txn["sku"], txn["type"], txn["reference_id"]), ("P1", "STOCK_IN", "PO-1"))
        self.assertEqual(self.export("/transactions/export", self.guest, type="STOCK_OUT"), [])
        adj = self.export("/adjustments/export", self.guest)[0]
        self.assertEqual((adj["quantity_change"], adj["reason"]), ("-1", "Damaged"))

    def test_only_exports_the_callers_company(self):
        product = self.add(Product(company_id=self.a, sku="SECRET", name="A's"))
        self.add(Transaction(company_id=self.a, product_id=product, user_id=self.owner, type="STOCK_IN", quantity=1))
        self.add(InventoryAdjustment(company_id=self.a, product_id=product, user_id=self.owner,
                                     quantity_change=1, reason="x"))
        for path in ("/products/export", "/transactions/export", "/adjustments/export"):
            with self.subTest(path=path):
                self.assertEqual(self.export(path, self.b_owner), [])

    def test_formula_cells_are_neutralised(self):
        self.add(Product(company_id=self.a, sku="P1", name='=HYPERLINK("http://evil")', reorder_level=0))
        self.assertTrue(self.export("/products/export", self.owner)[0]["name"].startswith("'="))

    def test_export_can_be_imported_by_another_company(self):
        self.add(Product(company_id=self.a, sku="P1", name="=Sum", price=1.5, current_stock=7))
        content = self.client.get(f"{API}/products/export", headers=self.auth(self.owner)).content
        response = self.client.post(f"{API}/products/import", headers=self.auth(self.b_owner),
                                    files={"file": ("p.csv", content, "text/csv")})
        self.assertEqual(response.status_code, 200, response.text)
        db = self.Session()
        try:
            copy = db.query(Product).filter_by(company_id=self.b).one()
            self.assertEqual((copy.name, copy.current_stock), ("=Sum", 7))
        finally:
            db.close()


class ImportTests(BasicsTestCase):
    def upload(self, text, user_id=None, dry_run=False, encoding="utf-8"):
        content = text if isinstance(text, bytes) else text.encode(encoding)
        return self.client.post(f"{API}/products/import", headers=self.auth(user_id or self.owner),
                                params={"dry_run": str(dry_run).lower()},
                                files={"file": ("products.csv", content, "text/csv")})

    def test_creates_products_stock_history_and_references(self):
        response = self.upload(HEADER
                               + "P1,Blue Mug,Nice,Kitchen,Acme,Bin 1,pcs,\"1,200.50\",5,25\n"
                               + "P2,Red Mug,,kitchen,,,,,,\n")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["products"], 2)
        self.assertEqual(body["opening_stock_units"], 25)
        self.assertEqual(body["new_categories"], ["Kitchen"])  # "kitchen" is the same one

        db = self.Session()
        try:
            mug = db.query(Product).filter_by(company_id=self.a, sku="P1").one()
            self.assertEqual(float(mug.price), 1200.50)
            self.assertEqual((mug.current_stock, mug.reorder_level, mug.unit), (25, 5, "pcs"))
            self.assertIsNotNone(mug.category_id)
            self.assertIsNotNone(mug.supplier_id)
            self.assertIsNotNone(mug.location_id)
            red = db.query(Product).filter_by(sku="P2").one()
            self.assertEqual(red.category_id, mug.category_id)
            self.assertEqual(red.current_stock, 0)
            txn = db.query(Transaction).filter_by(product_id=mug.id).one()
            self.assertEqual((txn.quantity, txn.user_id, txn.reference_type), (25, self.owner, "INITIAL"))
            self.assertEqual(db.query(Transaction).filter_by(product_id=red.id).count(), 0)
            self.assertEqual(db.query(AuditLog).filter_by(entity="PRODUCT", company_id=self.a).count(), 2)
        finally:
            db.close()

    def test_reuses_existing_references_case_insensitively(self):
        category = self.add(Category(company_id=self.a, name="Hardware"))
        response = self.upload(HEADER + "P1,Bolt,,HARDWARE,,,,,,\n")
        self.assertEqual(response.json()["new_categories"], [])
        self.assertEqual(self.get(Product, self._only_product_id()).category_id, category)

    def _only_product_id(self):
        db = self.Session()
        try:
            return db.query(Product.id).filter_by(company_id=self.a).scalar()
        finally:
            db.close()

    def test_any_bad_row_means_nothing_is_saved(self):
        self.add(Product(company_id=self.a, sku="TAKEN", name="Already here"))
        response = self.upload(HEADER
                               + "GOOD,Fine,,NewCat,,,,1,,\n"
                               + ",No SKU,,,,,,,,\n"
                               + "BADPRICE,Item,,,,,,free,,\n"
                               + "taken,Same SKU,,,,,,,,\n"
                               + "GOOD,Twice in file,,,,,,,,\n"
                               + "NEG,Item,,,,,,,,-1\n")
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertIn("Nothing was imported", body["detail"])
        problems = {(e["row"], e["field"]) for e in body["errors"]}
        self.assertEqual(problems, {(3, "sku"), (4, "price"), (5, "sku"), (6, "sku"), (7, "initial_stock")})
        self.assertEqual(self.count(Product, company_id=self.a), 1)
        self.assertEqual(self.count(Category, company_id=self.a), 0)

    def test_dry_run_reports_without_saving(self):
        response = self.upload(HEADER + "P1,Bolt,,NewCat,,,,,,3\n", dry_run=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["dry_run"])
        self.assertEqual(response.json()["new_categories"], ["NewCat"])
        self.assertEqual(self.count(Product, company_id=self.a), 0)
        self.assertEqual(self.count(Category, company_id=self.a), 0)

    def test_same_sku_and_names_are_fine_across_companies(self):
        self.add(Product(company_id=self.a, sku="P1", name="A's"))
        self.add(Category(company_id=self.a, name="Shared"))
        response = self.upload(HEADER + "P1,B's,,Shared,,,,,,\n", user_id=self.b_owner)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["new_categories"], ["Shared"])
        self.assertEqual(self.count(Category, company_id=self.b), 1)
        self.assertEqual(self.count(Product, company_id=self.a), 1)

    def test_only_writers_can_import(self):
        for user_id in (self.staff, self.guest):
            self.assertEqual(self.upload(HEADER + "P1,Bolt,,,,,,,,\n", user_id=user_id).status_code, 403)
        self.assertEqual(self.upload(HEADER + "P1,Bolt,,,,,,,,\n", user_id=self.manager).status_code, 200)

    def test_excel_encodings_and_header_styles(self):
        self.assertEqual(self.upload("﻿SKU, Name \nP1,Café\n").status_code, 200)
        self.assertEqual(self.upload("sku,name\nP2,Café\n", encoding="cp1252").status_code, 200)
        db = self.Session()
        try:
            names = {p.sku: p.name for p in db.query(Product).filter_by(company_id=self.a)}
        finally:
            db.close()
        self.assertEqual(names, {"P1": "Café", "P2": "Café"})

    def test_blank_rows_are_skipped_and_row_numbers_match_the_spreadsheet(self):
        response = self.upload("sku,name,price\nP1,Bolt,1\n,,\n\nP2,Nut,bad\n")
        self.assertEqual(response.json()["errors"][0]["row"], 5)

    def test_files_that_cannot_be_imported(self):
        too_many = "sku,name\n" + "".join(f"S{i},N\n" for i in range(MAX_ROWS + 1))
        for label, content in (
            ("missing column", "sku,price\nP1,1\n"),
            ("empty", ""),
            ("header only", "sku,name\n"),
            ("too many rows", too_many),
            ("too large", b"sku,name\n" + b"x" * (2 * 1024 * 1024 + 1)),
        ):
            with self.subTest(label):
                self.assertEqual(self.upload(content).status_code, 400)
        self.assertEqual(self.count(Product, company_id=self.a), 0)

    def test_reorder_level_must_fit_the_column(self):
        response = self.upload("sku,name,reorder_level\nP1,Bolt,99999999999\n")
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
