"""Company isolation: nothing in company A is visible to, or changeable by,
company B (its users or its API keys) or by the platform team.

Every route under /api/v1 must be listed in ROUTE_CLASSIFICATION at the
bottom, so a new endpoint fails test_every_route_is_classified until someone
decides how it is isolated and adds tests for it.
"""
import unittest

from app.main import app
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.company import Company
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.location import Location
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.transaction import Transaction
from app.models.user import User, UserRole
from support import PASSWORD, ApiTestCase

API = "/api/v1"
ALL_SCOPES = ("products:read", "products:create", "products:update", "products:delete")


class IsolationTestCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.platform_id = self.make_platform_admin()

        # Company A, full of data that B must never reach.
        self.a = self.make_company("Company A")
        self.a_owner = self.make_user(self.a, UserRole.OWNER)
        self.a_staff = self.make_user(self.a, UserRole.STAFF)
        self.a_category = self.add(Category(company_id=self.a, name="A Category"))
        self.a_supplier = self.add(Supplier(company_id=self.a, name="A Supplier"))
        self.a_location = self.add(Location(company_id=self.a, name="A Shelf", warehouse="A-WAREHOUSE"))
        self.a_product = self.add(Product(
            company_id=self.a, sku="SKU-1", name="A Widget", current_stock=10,
            category_id=self.a_category, supplier_id=self.a_supplier, location_id=self.a_location,
        ))
        self.a_txn = self.add(Transaction(company_id=self.a, product_id=self.a_product,
                                          user_id=self.a_owner, type="STOCK_IN", quantity=10))
        self.a_adj = self.add(InventoryAdjustment(company_id=self.a, product_id=self.a_product,
                                                  user_id=self.a_owner, quantity_change=1))
        self.a_log = self.add(AuditLog(company_id=self.a, user_id=self.a_owner, action="CREATE",
                                       entity="PRODUCT", entity_id=self.a_product))
        self.a_key, self.a_key_id = self.make_key(self.a, self.platform_id, ALL_SCOPES, name="A key")

        # Company B, the one trying to get in.
        self.b = self.make_company("Company B")
        self.b_owner = self.make_user(self.b, UserRole.OWNER)
        self.b_product = self.add(Product(company_id=self.b, sku="B-1", name="B Widget"))
        self.b_key, _ = self.make_key(self.b, self.platform_id, ALL_SCOPES, name="B key")

    def as_b(self):
        return self.auth(self.b_owner)

    def b_key_headers(self):
        return {"X-API-Key": self.b_key}

    def a_product_row(self):
        return self.get(Product, self.a_product)


class MemberIsolationTests(IsolationTestCase):
    def test_lists_never_include_another_companys_rows(self):
        a_ids = {self.a_product, self.a_category, self.a_supplier, self.a_location,
                 self.a_txn, self.a_adj, self.a_log, self.a_owner, self.a_staff}
        for path in ("/products", "/categories", "/suppliers", "/locations", "/transactions",
                     "/adjustments", "/audit-logs", "/users"):
            with self.subTest(path=path):
                response = self.client.get(API + path, headers=self.as_b())
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                rows = body["items"] if isinstance(body, dict) else body
                self.assertFalse({row["id"] for row in rows} & a_ids, f"{path} leaked company A rows")

    def test_warehouse_names_are_not_shared(self):
        response = self.client.get(f"{API}/locations/warehouses", headers=self.as_b())
        self.assertNotIn("A-WAREHOUSE", response.json())

    def test_reading_another_companys_row_by_id_is_404(self):
        for path in (
            f"/products/{self.a_product}",
            f"/categories/{self.a_category}",
            f"/categories/{self.a_category}/products",
            f"/suppliers/{self.a_supplier}",
            f"/suppliers/{self.a_supplier}/products",
            f"/locations/{self.a_location}",
            f"/locations/{self.a_location}/products",
            f"/transactions/{self.a_txn}",
            f"/adjustments/{self.a_adj}",
            f"/audit-logs/{self.a_log}",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(API + path, headers=self.as_b()).status_code, 404)

    def test_changing_another_companys_rows_is_404_and_changes_nothing(self):
        attempts = [
            ("patch", f"/products/{self.a_product}", {"name": "Hijacked"}),
            ("delete", f"/products/{self.a_product}", None),
            ("put", f"/categories/{self.a_category}", {"name": "Hijacked"}),
            ("delete", f"/categories/{self.a_category}", None),
            ("put", f"/suppliers/{self.a_supplier}", {"name": "Hijacked"}),
            ("delete", f"/suppliers/{self.a_supplier}", None),
            ("put", f"/locations/{self.a_location}", {"name": "Hijacked"}),
            ("delete", f"/locations/{self.a_location}", None),
            ("patch", f"/users/{self.a_staff}", {"is_active": False}),
        ]
        for method, path, body in attempts:
            with self.subTest(method=method, path=path):
                kwargs = {"headers": self.as_b()}
                if body is not None:
                    kwargs["json"] = body
                response = getattr(self.client, method)(API + path, **kwargs)
                self.assertEqual(response.status_code, 404, response.text)

        self.assertEqual(self.a_product_row().name, "A Widget")
        self.assertEqual(self.get(Category, self.a_category).name, "A Category")
        self.assertEqual(self.get(Supplier, self.a_supplier).name, "A Supplier")
        self.assertEqual(self.get(Location, self.a_location).name, "A Shelf")
        self.assertTrue(self.get(User, self.a_staff).is_active)

    def test_auth_user_routes_cannot_reach_another_company(self):
        for method, path, body in (
            ("post", "/auth/onboard", {"user_id": self.a_staff, "role": "GUEST", "is_active": False}),
            ("patch", "/auth/update-role", {"user_id": self.a_staff, "role": "GUEST"}),
            ("patch", "/auth/update-status", {"user_id": self.a_staff, "is_active": False}),
        ):
            with self.subTest(path=path):
                response = getattr(self.client, method)(API + path, json=body, headers=self.as_b())
                self.assertEqual(response.status_code, 404, response.text)
        staff = self.get(User, self.a_staff)
        self.assertEqual(staff.role, UserRole.STAFF)
        self.assertTrue(staff.is_active)

    def test_stock_of_another_companys_product_cannot_move(self):
        txn = self.client.post(f"{API}/transactions", headers=self.as_b(),
                               json={"product_id": self.a_product, "type": "STOCK_OUT", "quantity": 5})
        adj = self.client.post(f"{API}/adjustments", headers=self.as_b(),
                               json={"product_id": self.a_product, "quantity_change": -5, "reason": "x"})
        self.assertEqual(txn.status_code, 404, txn.text)
        self.assertEqual(adj.status_code, 404, adj.text)
        self.assertEqual(self.a_product_row().current_stock, 10)

    def test_products_cannot_point_at_another_companys_references(self):
        for field, ref in (("category_id", self.a_category), ("supplier_id", self.a_supplier),
                           ("location_id", self.a_location)):
            with self.subTest(field=field):
                created = self.client.post(f"{API}/products", headers=self.as_b(),
                                           json={"sku": f"NEW-{field}", "name": "New", field: ref})
                self.assertEqual(created.status_code, 400, created.text)
                updated = self.client.patch(f"{API}/products/{self.b_product}", headers=self.as_b(),
                                            json={field: ref})
                self.assertEqual(updated.status_code, 400, updated.text)

    def test_sku_is_unique_per_company_not_globally(self):
        same_sku = self.client.post(f"{API}/products", headers=self.as_b(),
                                    json={"sku": "SKU-1", "name": "B's own SKU-1"})
        self.assertEqual(same_sku.status_code, 201, same_sku.text)
        duplicate = self.client.post(f"{API}/products", headers=self.auth(self.a_owner),
                                     json={"sku": "SKU-1", "name": "Duplicate"})
        self.assertEqual(duplicate.status_code, 409)

    def test_category_names_are_unique_per_company_not_globally(self):
        response = self.client.post(f"{API}/categories", headers=self.as_b(),
                                    json={"name": "A Category"})
        self.assertEqual(response.status_code, 201, response.text)

    def test_counts_only_include_own_products(self):
        cat = self.client.post(f"{API}/categories", headers=self.as_b(), json={"name": "B Cat"}).json()
        self.assertEqual(cat["product_count"], 0)
        a_view = self.client.get(f"{API}/categories/{self.a_category}", headers=self.auth(self.a_owner))
        self.assertEqual(a_view.json()["product_count"], 1)

    def test_new_rows_belong_to_the_creators_company(self):
        product = self.client.post(f"{API}/products", headers=self.as_b(),
                                   json={"sku": "B-2", "name": "Mine", "initial_stock": 3}).json()
        user = self.client.post(f"{API}/users", headers=self.as_b(),
                                json={"name": "New Hire", "email": "hire@b.example.com",
                                      "password": "Password123", "role": "STAFF"}).json()
        self.assertEqual(self.get(Product, product["id"]).company_id, self.b)
        self.assertEqual(self.get(User, user["id"]).company_id, self.b)
        db = self.Session()
        try:
            txn = db.query(Transaction).filter(Transaction.product_id == product["id"]).one()
            self.assertEqual(txn.company_id, self.b)
        finally:
            db.close()

    def test_audit_rows_are_written_to_the_actors_company(self):
        self.client.post(f"{API}/categories", headers=self.as_b(), json={"name": "Audited"})
        db = self.Session()
        try:
            row = db.query(AuditLog).filter(AuditLog.entity == "CATEGORY").one()
            self.assertEqual(row.company_id, self.b)
        finally:
            db.close()


class ApiKeyIsolationTests(IsolationTestCase):
    def test_partner_lists_only_show_the_keys_company(self):
        for path, a_id in (("/integration/products", self.a_product),
                           ("/integration/categories", self.a_category),
                           ("/integration/suppliers", self.a_supplier),
                           ("/integration/locations", self.a_location)):
            with self.subTest(path=path):
                response = self.client.get(API + path, headers=self.b_key_headers())
                self.assertEqual(response.status_code, 200, response.text)
                self.assertNotIn(a_id, {row["id"] for row in response.json()})

    def test_partner_cannot_touch_another_companys_product(self):
        url = f"{API}/integration/products/{self.a_product}"
        self.assertEqual(self.client.get(url, headers=self.b_key_headers()).status_code, 404)
        self.assertEqual(self.client.patch(url, headers=self.b_key_headers(),
                                           json={"name": "Hijacked"}).status_code, 404)
        self.assertEqual(self.client.delete(url, headers=self.b_key_headers()).status_code, 404)
        self.assertEqual(self.a_product_row().name, "A Widget")

    def test_partner_cannot_reference_another_companys_category(self):
        response = self.client.post(f"{API}/integration/products", headers=self.b_key_headers(),
                                    json={"sku": "P-1", "name": "Partner", "category_id": self.a_category})
        self.assertEqual(response.status_code, 400, response.text)

    def test_partner_writes_are_attributed_to_the_key_not_a_person(self):
        created = self.client.post(f"{API}/integration/products", headers={"X-API-Key": self.a_key},
                                   json={"sku": "P-2", "name": "Via partner", "initial_stock": 4})
        self.assertEqual(created.status_code, 201, created.text)
        product_id = created.json()["id"]

        db = self.Session()
        try:
            txn = db.query(Transaction).filter(Transaction.product_id == product_id).one()
            self.assertIsNone(txn.user_id)
            self.assertEqual(txn.api_key_id, self.a_key_id)
            self.assertEqual(txn.company_id, self.a)
            audit = db.query(AuditLog).filter(AuditLog.entity_id == product_id).one()
            self.assertIsNone(audit.user_id)
            self.assertEqual(audit.company_id, self.a)
            self.assertEqual(audit.details["api_key_id"], self.a_key_id)
        finally:
            db.close()

        ledger = self.client.get(f"{API}/transactions", headers=self.auth(self.a_owner),
                                 params={"product_id": product_id}).json()["items"]
        self.assertEqual(ledger[0]["api_key_name"], "A key")
        self.assertIsNone(ledger[0]["user_name"])


class PlatformAdminTests(IsolationTestCase):
    def as_platform(self):
        return self.auth(self.platform_id)

    def test_platform_team_cannot_see_company_inventory(self):
        for path in ("/products", f"/products/{self.a_product}", "/categories", "/suppliers",
                     "/locations", "/transactions", "/adjustments", "/audit-logs", "/users",
                     "/company"):
            with self.subTest(path=path):
                response = self.client.get(API + path, headers=self.as_platform())
                self.assertEqual(response.status_code, 403, response.text)

    def test_platform_team_manages_companies(self):
        listed = self.client.get(f"{API}/platform/companies", headers=self.as_platform())
        self.assertEqual(listed.status_code, 200)
        by_id = {c["id"]: c for c in listed.json()["items"]}
        self.assertEqual(by_id[self.a]["member_count"], 2)

    def test_platform_audit_log_hides_company_inventory_activity(self):
        logs = self.client.get(f"{API}/platform/audit-logs", headers=self.as_platform()).json()
        self.assertNotIn(self.a_log, {row["id"] for row in logs["items"]})

    def test_company_members_cannot_use_platform_routes(self):
        for method, path in (("get", "/platform/companies"), ("get", "/platform/audit-logs"),
                             ("get", "/api-keys"), ("patch", "/roles/GUEST")):
            with self.subTest(path=path):
                kwargs = {"json": {"description": "x"}} if method == "patch" else {}
                response = getattr(self.client, method)(API + path, headers=self.auth(self.a_owner), **kwargs)
                self.assertEqual(response.status_code, 403, response.text)

    def test_keys_are_issued_to_a_company(self):
        response = self.client.post(f"{API}/api-keys", headers=self.as_platform(),
                                    json={"company_id": self.b, "name": "Issued"})
        self.assertEqual(response.status_code, 201, response.text)
        raw_key = response.json()["api_key"]
        products = self.client.get(f"{API}/integration/products", headers={"X-API-Key": raw_key}).json()
        self.assertEqual({p["id"] for p in products}, {self.b_product})

    def test_keys_cannot_be_issued_to_a_missing_or_inactive_company(self):
        inactive = self.make_company("Gone", is_active=False)
        for company_id in ("no-such-company", inactive):
            with self.subTest(company_id=company_id):
                response = self.client.post(f"{API}/api-keys", headers=self.as_platform(),
                                            json={"company_id": company_id, "name": "Nope"})
                self.assertEqual(response.status_code, 400)


class DeactivatedCompanyTests(IsolationTestCase):
    def deactivate_a(self):
        response = self.client.patch(f"{API}/platform/companies/{self.a}",
                                     headers=self.auth(self.platform_id), json={"is_active": False})
        self.assertEqual(response.status_code, 200, response.text)

    def test_members_are_locked_out(self):
        self.deactivate_a()
        self.assertEqual(self.client.get(f"{API}/products", headers=self.auth(self.a_owner)).status_code, 403)
        a_email = self.get(User, self.a_owner).email
        login = self.client.post(f"{API}/auth/login", json={"email": a_email, "password": PASSWORD})
        self.assertEqual(login.status_code, 403)

    def test_api_keys_stop_working_immediately(self):
        self.deactivate_a()
        response = self.client.get(f"{API}/integration/products", headers={"X-API-Key": self.a_key})
        self.assertEqual(response.status_code, 401)
        db = self.Session()
        try:
            failure = db.query(AuditLog).filter(AuditLog.action == "API_KEY_AUTH_FAILED").one()
            self.assertEqual(failure.details["reason"], "company_inactive")
            self.assertEqual(failure.company_id, self.a)
        finally:
            db.close()

    def test_other_companies_are_unaffected(self):
        self.deactivate_a()
        self.assertEqual(self.client.get(f"{API}/products", headers=self.as_b()).status_code, 200)
        self.assertEqual(self.client.get(f"{API}/integration/products",
                                         headers=self.b_key_headers()).status_code, 200)

    def test_reactivating_restores_access(self):
        self.deactivate_a()
        self.client.patch(f"{API}/platform/companies/{self.a}",
                          headers=self.auth(self.platform_id), json={"is_active": True})
        self.assertEqual(self.client.get(f"{API}/products", headers=self.auth(self.a_owner)).status_code, 200)


class SignUpTests(ApiTestCase):
    def register(self, email, company):
        return self.client.post(f"{API}/auth/register", json={
            "name": "Founder", "email": email, "password": "Password123", "company_name": company,
        })

    def login(self, email):
        tokens = self.client.post(f"{API}/auth/login", json={"email": email, "password": "Password123"})
        return {"Authorization": f"Bearer {tokens.json()['access_token']}"}

    def test_registering_creates_a_company_with_you_as_owner(self):
        response = self.register("founder@one.example.com", "  One Inc  ")
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["role"], "OWNER")
        self.assertEqual(self.get(Company, body["company_id"]).name, "One Inc")

        headers = self.login("founder@one.example.com")
        me = self.client.get(f"{API}/company", headers=headers)
        self.assertEqual(me.json()["name"], "One Inc")

    def test_two_sign_ups_get_separate_companies(self):
        self.register("one@example.com", "One")
        self.register("two@example.com", "Two")
        one, two = self.login("one@example.com"), self.login("two@example.com")
        self.client.post(f"{API}/products", headers=one, json={"sku": "S", "name": "One's"})
        self.assertEqual(self.client.get(f"{API}/products", headers=two).json(), [])

    def test_company_name_is_required(self):
        response = self.client.post(f"{API}/auth/register", json={
            "name": "Founder", "email": "x@example.com", "password": "Password123"})
        self.assertEqual(response.status_code, 422)

    def test_only_the_owner_can_rename_the_company(self):
        company = self.make_company("Old")
        owner, admin = self.make_user(company, UserRole.OWNER), self.make_user(company, UserRole.ADMIN)
        denied = self.client.patch(f"{API}/company", headers=self.auth(admin), json={"name": "New"})
        self.assertEqual(denied.status_code, 403)
        renamed = self.client.patch(f"{API}/company", headers=self.auth(owner), json={"name": "New"})
        self.assertEqual(renamed.json()["name"], "New")


class OwnerRoleTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.company = self.make_company()
        self.owner = self.make_user(self.company, UserRole.OWNER)
        self.admin = self.make_user(self.company, UserRole.ADMIN)
        self.staff = self.make_user(self.company, UserRole.STAFF)

    def patch_user(self, actor, target, body):
        return self.client.patch(f"{API}/users/{target}", headers=self.auth(actor), json=body)

    def test_admin_cannot_create_or_promote_owners(self):
        created = self.client.post(f"{API}/users", headers=self.auth(self.admin), json={
            "name": "X", "email": "x@example.com", "password": "Password123", "role": "OWNER"})
        self.assertEqual(created.status_code, 403)
        self.assertEqual(self.patch_user(self.admin, self.staff, {"role": "OWNER"}).status_code, 403)

    def test_admin_cannot_modify_an_owner(self):
        self.assertEqual(self.patch_user(self.admin, self.owner, {"is_active": False}).status_code, 403)
        self.assertTrue(self.get(User, self.owner).is_active)

    def test_owner_can_promote_another_owner(self):
        response = self.patch_user(self.owner, self.admin, {"role": "OWNER"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.get(User, self.admin).role, UserRole.OWNER)

    def test_owner_cannot_demote_or_deactivate_themselves(self):
        self.assertEqual(self.patch_user(self.owner, self.owner, {"role": "ADMIN"}).status_code, 400)
        self.assertEqual(self.patch_user(self.owner, self.owner, {"is_active": False}).status_code, 400)

    def test_owner_has_admin_access(self):
        self.assertEqual(self.client.get(f"{API}/audit-logs", headers=self.auth(self.owner)).status_code, 200)


# Every /api/v1 route and how it is kept inside one company.
ROUTE_CLASSIFICATION = {
    # Public or about the caller's own account.
    ("POST", "/auth/register"): "public",
    ("POST", "/auth/login"): "public",
    ("POST", "/auth/refresh"): "public",
    ("GET", "/auth/me"): "self",
    # Company data, scoped by the member's company_id (tested above).
    **{(m, p): "member" for m, p in (
        ("POST", "/auth/onboard"), ("PATCH", "/auth/update-role"), ("PATCH", "/auth/update-status"),
        ("GET", "/users"), ("POST", "/users"), ("PATCH", "/users/{user_id}"), ("GET", "/roles"),
        ("GET", "/products"), ("POST", "/products"), ("GET", "/products/{product_id}"),
        ("PATCH", "/products/{product_id}"), ("DELETE", "/products/{product_id}"),
        ("GET", "/categories"), ("POST", "/categories"), ("GET", "/categories/{category_id}"),
        ("GET", "/categories/{category_id}/products"), ("PUT", "/categories/{category_id}"),
        ("DELETE", "/categories/{category_id}"),
        ("GET", "/suppliers"), ("POST", "/suppliers"), ("GET", "/suppliers/{supplier_id}"),
        ("GET", "/suppliers/{supplier_id}/products"), ("PUT", "/suppliers/{supplier_id}"),
        ("DELETE", "/suppliers/{supplier_id}"),
        ("GET", "/locations"), ("POST", "/locations"), ("GET", "/locations/warehouses"),
        ("GET", "/locations/{location_id}"), ("GET", "/locations/{location_id}/products"),
        ("PUT", "/locations/{location_id}"), ("DELETE", "/locations/{location_id}"),
        ("GET", "/transactions"), ("POST", "/transactions"), ("GET", "/transactions/{transaction_id}"),
        ("GET", "/adjustments"), ("POST", "/adjustments"), ("GET", "/adjustments/{adjustment_id}"),
        ("GET", "/audit-logs"), ("GET", "/audit-logs/{log_id}"),
        ("GET", "/company"), ("PATCH", "/company"),
    )},
    # Company data, scoped by the API key's company_id (tested above).
    **{(m, p): "api_key" for m, p in (
        ("GET", "/integration/products"), ("POST", "/integration/products"),
        ("GET", "/integration/products/{product_id}"), ("PATCH", "/integration/products/{product_id}"),
        ("DELETE", "/integration/products/{product_id}"), ("GET", "/integration/categories"),
        ("GET", "/integration/suppliers"), ("GET", "/integration/locations"),
    )},
    # Platform team only; no company inventory behind them.
    **{(m, p): "platform" for m, p in (
        ("PATCH", "/roles/{role_name}"),
        ("GET", "/api-keys"), ("POST", "/api-keys"), ("DELETE", "/api-keys/{api_key_id}"),
        ("GET", "/platform/companies"), ("GET", "/platform/companies/{company_id}"),
        ("PATCH", "/platform/companies/{company_id}"),
        ("GET", "/platform/audit-logs"), ("GET", "/platform/audit-logs/{log_id}"),
    )},
}


class RouteCoverageTests(unittest.TestCase):
    def test_every_route_is_classified(self):
        # The OpenAPI schema is FastAPI's public list of every exposed route.
        actual = {
            (method.upper(), path.removeprefix(API))
            for path, operations in app.openapi()["paths"].items()
            if path.startswith(API)
            for method in operations
        }
        unclassified = actual - ROUTE_CLASSIFICATION.keys()
        self.assertFalse(
            unclassified,
            "New routes need company isolation tests and an entry in ROUTE_CLASSIFICATION: "
            f"{sorted(unclassified)}",
        )
        self.assertFalse(ROUTE_CLASSIFICATION.keys() - actual, "ROUTE_CLASSIFICATION lists removed routes")


if __name__ == "__main__":
    unittest.main()
