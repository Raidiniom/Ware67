"""API-level tests for the partner API key lifecycle and authenticating with keys.

Runs the real FastAPI app against an in-memory SQLite database, so no
tunnel or shared MySQL is needed:  python -m unittest discover -s tests
"""
import hashlib
import unittest
from datetime import datetime, timedelta
from unittest import mock

from starlette.requests import Request

from app.api import deps
from app.core.config import settings
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.models.user import UserRole
from app.services.api_keys import generate_api_key, hash_api_key
from app.services.audit import client_ip
from app.services.rate_limit import FixedWindowLimiter
from support import ApiTestCase, utcnow

PRODUCTS = "/api/v1/integration/products"
COMPANY_KEYS = "/api/v1/company/api-keys"
PLATFORM_KEYS = "/api/v1/platform/api-keys"


class ApiKeyTestCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.company_id = self.make_company()
        self.owner_id = self.make_user(self.company_id, UserRole.OWNER)
        # Requests are reviewed by the platform team.
        self.admin_id = self.make_platform_admin()
        self.add(Product(company_id=self.company_id, sku="SKU-1", name="Widget", current_stock=10))

    def admin_auth(self):
        return self.auth(self.admin_id)

    def make_key(self, scopes=("products:read",), **fields):
        """Inserts a key for this test's company and returns (raw_key, key_id)."""
        return super().make_key(self.company_id, self.owner_id, scopes, **fields)

    def get_key(self, key_id):
        db = self.Session()
        try:
            return db.get(ApiKey, key_id)
        finally:
            db.close()

    def failed_audits(self):
        db = self.Session()
        try:
            rows = db.query(AuditLog).filter(AuditLog.action == "API_KEY_AUTH_FAILED").all()
            return [row.details for row in rows]
        finally:
            db.close()


class ApiKeyAuthenticationTests(ApiKeyTestCase):
    def test_valid_key_is_accepted(self):
        raw_key, key_id = self.make_key()
        response = self.client.get(PRODUCTS, headers={"X-API-Key": raw_key})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["sku"], "SKU-1")
        self.assertIsNotNone(self.get_key(key_id).last_used_at)

    def test_missing_key_is_rejected_without_an_audit_row(self):
        response = self.client.get(PRODUCTS)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.failed_audits(), [])

    def test_malformed_key_is_rejected_and_audited(self):
        response = self.client.get(PRODUCTS, headers={"X-API-Key": "not-a-ware67-key"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.failed_audits(), [{"reason": "malformed", "key_prefix": None}])

    def test_unknown_prefix_is_rejected(self):
        raw_key, prefix, _ = generate_api_key()  # never stored
        response = self.client.get(PRODUCTS, headers={"X-API-Key": raw_key})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.failed_audits(), [{"reason": "unknown", "key_prefix": prefix}])

    def test_wrong_secret_for_a_real_prefix_is_rejected(self):
        raw_key, _ = self.make_key()
        response = self.client.get(PRODUCTS, headers={"X-API-Key": raw_key[:-4] + "AAAA"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid or missing API key")
        [audit] = self.failed_audits()
        self.assertEqual(audit["reason"], "bad_secret")

    def test_audit_never_contains_the_submitted_key(self):
        raw_key, _ = self.make_key()
        self.client.get(PRODUCTS, headers={"X-API-Key": raw_key[:-4] + "AAAA"})
        secret = raw_key.split("_", 2)[2]
        self.assertNotIn(secret[:-4], repr(self.failed_audits()))

    def test_revoked_key_is_rejected(self):
        raw_key, _ = self.make_key(status=ApiKeyStatus.REVOKED, revoked_at=utcnow())
        response = self.client.get(PRODUCTS, headers={"X-API-Key": raw_key})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid or missing API key")
        self.assertEqual(self.failed_audits()[0]["reason"], "revoked")

    def test_expired_key_is_rejected(self):
        raw_key, _ = self.make_key(expires_at=utcnow() - timedelta(seconds=1))
        response = self.client.get(PRODUCTS, headers={"X-API-Key": raw_key})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "API key has expired")
        self.assertEqual(self.failed_audits()[0]["reason"], "expired")

    def test_key_without_the_required_scope_is_forbidden(self):
        raw_key, _ = self.make_key(scopes=["products:read"])
        response = self.client.post(
            PRODUCTS, headers={"X-API-Key": raw_key}, json={"sku": "SKU-2", "name": "Gadget"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("products:create", response.json()["detail"])

    def test_user_tokens_are_not_accepted_on_integration_routes(self):
        response = self.client.get(PRODUCTS, headers=self.admin_auth())
        self.assertEqual(response.status_code, 401)

    def test_last_used_at_is_not_rewritten_on_every_request(self):
        recent = utcnow() - timedelta(minutes=1)
        raw_key, key_id = self.make_key(last_used_at=recent)
        self.client.get(PRODUCTS, headers={"X-API-Key": raw_key})
        self.assertEqual(self.get_key(key_id).last_used_at, recent)

    def test_stale_last_used_at_is_refreshed(self):
        stale = utcnow() - timedelta(minutes=10)
        raw_key, key_id = self.make_key(last_used_at=stale)
        self.client.get(PRODUCTS, headers={"X-API-Key": raw_key})
        self.assertGreater(self.get_key(key_id).last_used_at, stale)


class ApiKeyRateLimitTests(ApiKeyTestCase):
    def test_key_is_rate_limited_per_minute(self):
        raw_key, _ = self.make_key()
        with mock.patch.object(deps.api_key_limiter, "limit", 2):
            codes = [self.client.get(PRODUCTS, headers={"X-API-Key": raw_key}) for _ in range(3)]
        self.assertEqual([r.status_code for r in codes], [200, 200, 429])
        self.assertGreater(int(codes[2].headers["Retry-After"]), 0)

    def test_failed_attempts_are_limited_and_stop_being_audited(self):
        with mock.patch.object(deps.failed_attempt_limiter, "limit", 2):
            codes = [
                self.client.get(PRODUCTS, headers={"X-API-Key": "bad"}).status_code
                for _ in range(4)
            ]
        self.assertEqual(codes, [401, 401, 429, 429])
        self.assertEqual(len(self.failed_audits()), 2)

    def test_failures_from_an_ip_do_not_lock_out_a_valid_key(self):
        raw_key, _ = self.make_key()
        with mock.patch.object(deps.failed_attempt_limiter, "limit", 1):
            self.client.get(PRODUCTS, headers={"X-API-Key": "bad"})
            self.client.get(PRODUCTS, headers={"X-API-Key": "bad"})
            response = self.client.get(PRODUCTS, headers={"X-API-Key": raw_key})
        self.assertEqual(response.status_code, 200)

    def test_limiter_resets_in_the_next_window(self):
        limiter = FixedWindowLimiter(limit=1, window_seconds=60)
        with mock.patch("app.services.rate_limit.time.time", return_value=120.0):
            self.assertIsNone(limiter.hit("k"))
            self.assertEqual(limiter.hit("k"), 60)
        with mock.patch("app.services.rate_limit.time.time", return_value=180.0):
            self.assertIsNone(limiter.hit("k"))


class ApiKeyLifecycleTests(ApiKeyTestCase):
    """Request (company) -> approve/reject (platform) -> reveal once (company)."""

    def request_key(self, user_id=None, **body):
        body = {"name": "Partner", "scopes": ["products:read"], **body}
        return self.client.post(COMPANY_KEYS, headers=self.auth(user_id or self.owner_id), json=body)

    def approve(self, key_id, **body):
        return self.client.post(f"{PLATFORM_KEYS}/{key_id}/approve", headers=self.admin_auth(), json=body)

    def reject(self, key_id, reason="Not needed"):
        return self.client.post(f"{PLATFORM_KEYS}/{key_id}/reject", headers=self.admin_auth(),
                                json={"reason": reason})

    def reveal(self, key_id, user_id=None):
        return self.client.post(f"{COMPANY_KEYS}/{key_id}/reveal", headers=self.auth(user_id or self.owner_id))

    def issued_key(self, scopes=("products:read",)):
        """Runs the whole flow and returns (raw_key, key_id)."""
        key_id = self.request_key(scopes=list(scopes)).json()["id"]
        self.approve(key_id)
        return self.reveal(key_id).json()["api_key"], key_id

    def company_view(self, key_id):
        keys = self.client.get(COMPANY_KEYS, headers=self.auth(self.owner_id)).json()["items"]
        return next(k for k in keys if k["id"] == key_id)

    def set_fields(self, key_id, **fields):
        db = self.Session()
        try:
            key = db.get(ApiKey, key_id)
            for name, value in fields.items():
                setattr(key, name, value)
            db.commit()
        finally:
            db.close()

    # --- the happy path -------------------------------------------------

    def test_request_approve_reveal_then_use(self):
        requested = self.request_key(purpose="Sync our shop", scopes=["products:read"])
        self.assertEqual(requested.status_code, 201, requested.text)
        self.assertEqual(requested.json()["status"], "PENDING")
        self.assertIsNone(requested.json()["key_prefix"])
        key_id = requested.json()["id"]

        approved = self.approve(key_id)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "APPROVED")
        deadline = datetime.fromisoformat(approved.json()["reveal_deadline"])
        self.assertAlmostEqual((deadline - utcnow()).total_seconds(), timedelta(days=7).total_seconds(), delta=60)

        revealed = self.reveal(key_id)
        self.assertEqual(revealed.status_code, 200, revealed.text)
        body = revealed.json()
        self.assertEqual(body["status"], "ACTIVE")
        self.assertRegex(body["key_prefix"], r"^ware67_[0-9a-f]{12}$")
        expires_at = datetime.fromisoformat(body["expires_at"])
        self.assertAlmostEqual((expires_at - utcnow()).total_seconds(), timedelta(days=90).total_seconds(), delta=60)

        raw_key = body["api_key"]
        self.assertEqual(self.get_key(key_id).key_hash, hashlib.sha256(raw_key.encode()).hexdigest())
        self.assertEqual(self.client.get(PRODUCTS, headers={"X-API-Key": raw_key}).status_code, 200)

    def test_no_secret_exists_before_reveal(self):
        key_id = self.request_key().json()["id"]
        self.approve(key_id)
        stored = self.get_key(key_id)
        self.assertIsNone(stored.key_hash)
        self.assertIsNone(stored.key_prefix)

    def test_a_key_can_only_be_revealed_once(self):
        _, key_id = self.issued_key()
        again = self.reveal(key_id)
        self.assertEqual(again.status_code, 409)
        self.assertNotIn("api_key", again.json())

    def test_pending_request_cannot_be_revealed(self):
        key_id = self.request_key().json()["id"]
        self.assertEqual(self.reveal(key_id).status_code, 409)

    # --- what the platform team can grant -------------------------------

    def test_platform_can_grant_fewer_scopes_than_requested(self):
        key_id = self.request_key(scopes=["products:read", "products:create"]).json()["id"]
        approved = self.approve(key_id, scopes=["products:read"])
        self.assertEqual(approved.json()["scopes"], ["products:read"])
        raw_key = self.reveal(key_id).json()["api_key"]
        create = self.client.post(PRODUCTS, headers={"X-API-Key": raw_key}, json={"sku": "X", "name": "X"})
        self.assertEqual(create.status_code, 403)

    def test_platform_cannot_grant_scopes_nobody_asked_for(self):
        key_id = self.request_key(scopes=["products:read"]).json()["id"]
        self.assertEqual(self.approve(key_id, scopes=["products:delete"]).status_code, 400)
        self.assertEqual(self.get_key(key_id).status, ApiKeyStatus.PENDING)

    def test_rejected_request_shows_the_reason_and_cannot_be_revealed(self):
        key_id = self.request_key().json()["id"]
        self.assertEqual(self.reject(key_id, "Use read-only scopes").status_code, 200)
        view = self.company_view(key_id)
        self.assertEqual(view["status"], "REJECTED")
        self.assertEqual(view["rejection_reason"], "Use read-only scopes")
        self.assertEqual(self.reveal(key_id).status_code, 409)

    def test_only_pending_requests_can_be_reviewed(self):
        key_id = self.request_key().json()["id"]
        self.approve(key_id)
        self.assertEqual(self.approve(key_id).status_code, 409)
        self.assertEqual(self.reject(key_id).status_code, 409)

    def test_cannot_approve_for_a_deactivated_company(self):
        key_id = self.request_key().json()["id"]
        self.client.patch(f"/api/v1/platform/companies/{self.company_id}", headers=self.admin_auth(),
                          json={"is_active": False})
        self.assertEqual(self.approve(key_id).status_code, 409)

    # --- time limits ----------------------------------------------------

    def test_approval_lapses_if_not_revealed_in_time(self):
        key_id = self.request_key().json()["id"]
        self.approve(key_id)
        self.set_fields(key_id, reveal_deadline=utcnow() - timedelta(seconds=1))
        self.assertEqual(self.company_view(key_id)["status"], "LAPSED")
        self.assertEqual(self.reveal(key_id).status_code, 409)
        self.assertEqual(self.get_key(key_id).status, ApiKeyStatus.LAPSED)

    def test_expired_key_shows_as_expired(self):
        _, key_id = self.issued_key()
        self.set_fields(key_id, expires_at=utcnow() - timedelta(seconds=1))
        self.assertEqual(self.company_view(key_id)["status"], "EXPIRED")

    def test_expiring_list_shows_keys_ending_soon(self):
        _, soon = self.issued_key()
        _, later = self.issued_key()
        _, revoked = self.issued_key()
        self.set_fields(soon, expires_at=utcnow() + timedelta(days=5))
        self.set_fields(later, expires_at=utcnow() + timedelta(days=30))
        self.set_fields(revoked, expires_at=utcnow() + timedelta(days=5), status=ApiKeyStatus.REVOKED)

        def expiring(days):
            response = self.client.get(f"{PLATFORM_KEYS}/expiring", headers=self.admin_auth(),
                                       params={"days": days})
            return [k["id"] for k in response.json()["items"]]

        self.assertEqual(expiring(14), [soon])
        self.assertEqual(expiring(60), [soon, later])

    # --- revoking -------------------------------------------------------

    def test_company_can_withdraw_a_request(self):
        key_id = self.request_key().json()["id"]
        response = self.client.delete(f"{COMPANY_KEYS}/{key_id}", headers=self.auth(self.owner_id))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.approve(key_id).status_code, 409)

    def test_company_can_revoke_its_own_live_key(self):
        raw_key, key_id = self.issued_key()
        url = f"{COMPANY_KEYS}/{key_id}"
        self.assertEqual(self.client.delete(url, headers=self.auth(self.owner_id)).status_code, 204)
        self.assertEqual(self.client.delete(url, headers=self.auth(self.owner_id)).status_code, 409)
        self.assertEqual(self.client.get(PRODUCTS, headers={"X-API-Key": raw_key}).status_code, 401)

    def test_platform_can_revoke_any_key(self):
        raw_key, key_id = self.issued_key()
        response = self.client.delete(f"{PLATFORM_KEYS}/{key_id}", headers=self.admin_auth())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(PRODUCTS, headers={"X-API-Key": raw_key}).status_code, 401)
        self.assertEqual(self.get_key(key_id).revoked_by, self.admin_id)

    # --- who may do what ------------------------------------------------

    def test_only_owners_and_admins_manage_company_keys(self):
        admin = self.make_user(self.company_id, UserRole.ADMIN)
        manager = self.make_user(self.company_id, UserRole.MANAGER)
        self.assertEqual(self.request_key(admin).status_code, 201)
        self.assertEqual(self.request_key(manager).status_code, 403)
        self.assertEqual(self.client.get(COMPANY_KEYS, headers=self.auth(manager)).status_code, 403)

    def test_platform_team_cannot_request_or_reveal(self):
        self.assertEqual(self.request_key(self.admin_id).status_code, 403)
        key_id = self.request_key().json()["id"]
        self.approve(key_id)
        self.assertEqual(self.reveal(key_id, self.admin_id).status_code, 403)

    def test_companies_cannot_review_their_own_requests(self):
        key_id = self.request_key().json()["id"]
        response = self.client.post(f"{PLATFORM_KEYS}/{key_id}/approve", headers=self.auth(self.owner_id), json={})
        self.assertEqual(response.status_code, 403)

    def test_platform_team_never_sees_the_secret(self):
        raw_key, key_id = self.issued_key()
        secret = raw_key.split("_", 2)[2]
        platform_view = self.client.get(f"{PLATFORM_KEYS}/{key_id}", headers=self.admin_auth()).json()
        listing = self.client.get(PLATFORM_KEYS, headers=self.admin_auth()).text
        audits = self.client.get("/api/v1/platform/audit-logs", headers=self.admin_auth()).text
        for text in (repr(platform_view), listing, audits):
            self.assertNotIn(secret, text)
        self.assertNotIn("key_hash", platform_view)

    # --- housekeeping ---------------------------------------------------

    def test_open_requests_are_capped(self):
        with mock.patch.object(settings, "API_KEY_MAX_OPEN_REQUESTS", 2):
            self.assertEqual(self.request_key().status_code, 201)
            self.assertEqual(self.request_key().status_code, 201)
            self.assertEqual(self.request_key().status_code, 409)

    def test_review_queue_is_oldest_first(self):
        first = self.request_key(name="First").json()["id"]
        second = self.request_key(name="Second").json()["id"]
        self.set_fields(first, created_at=utcnow() - timedelta(hours=1))
        queue = self.client.get(PLATFORM_KEYS, headers=self.admin_auth(), params={"status": "PENDING"}).json()
        self.assertEqual([k["id"] for k in queue["items"]], [first, second])
        self.assertEqual(queue["items"][0]["company_name"], "Acme")

    def test_company_list_is_paginated(self):
        for _ in range(3):
            self.make_key()
        page = self.client.get(COMPANY_KEYS, headers=self.auth(self.owner_id), params={"skip": 1, "limit": 2})
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(page.json()["items"]), 2)
        self.assertEqual(page.json()["total"], 3)

    def test_every_step_is_audited(self):
        raw_key, key_id = self.issued_key()
        self.client.delete(f"{COMPANY_KEYS}/{key_id}", headers=self.auth(self.owner_id))
        db = self.Session()
        try:
            rows = (db.query(AuditLog).filter(AuditLog.entity_id == key_id)
                    .order_by(AuditLog.created_at, AuditLog.action).all())
            self.assertEqual({r.action for r in rows}, {"REQUEST", "APPROVE", "REVEAL", "REVOKE"})
            self.assertTrue(all(r.company_id == self.company_id for r in rows))
            self.assertNotIn(raw_key.split("_", 2)[2], repr([r.details for r in rows]))
        finally:
            db.close()

    def test_hash_does_not_depend_on_the_jwt_secret(self):
        raw_key, _, key_hash = generate_api_key()
        with mock.patch.object(settings, "JWT_SECRET_KEY", "rotated-secret"):
            self.assertEqual(hash_api_key(raw_key), key_hash)

    def test_prefix_collision_is_retried(self):
        taken_raw, taken_prefix, taken_hash = generate_api_key()
        self.make_key()  # an unrelated key, so the table isn't empty
        self.set_fields(self.make_key()[1], key_prefix=taken_prefix, key_hash=taken_hash)

        key_id = self.request_key().json()["id"]
        self.approve(key_id)
        fresh = generate_api_key()
        with mock.patch("app.services.api_keys.generate_api_key",
                        side_effect=[(taken_raw, taken_prefix, taken_hash), fresh]):
            revealed = self.reveal(key_id)
        self.assertEqual(revealed.status_code, 200, revealed.text)
        self.assertEqual(revealed.json()["key_prefix"], fresh[1])


class ClientIpTests(unittest.TestCase):
    def request(self, peer, forwarded=None):
        headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
        return Request({"type": "http", "client": (peer, 1234), "headers": headers})

    def test_forwarded_header_is_ignored_without_trusted_proxies(self):
        with mock.patch.object(settings, "TRUSTED_PROXIES", ""):
            self.assertEqual(client_ip(self.request("203.0.113.9", "1.2.3.4")), "203.0.113.9")

    def test_forwarded_header_is_ignored_from_an_untrusted_peer(self):
        with mock.patch.object(settings, "TRUSTED_PROXIES", "10.0.0.1"):
            self.assertEqual(client_ip(self.request("203.0.113.9", "1.2.3.4")), "203.0.113.9")

    def test_trusted_proxy_forwards_the_real_client(self):
        with mock.patch.object(settings, "TRUSTED_PROXIES", "10.0.0.1"):
            self.assertEqual(client_ip(self.request("10.0.0.1", "198.51.100.7")), "198.51.100.7")

    def test_spoofed_entries_left_of_the_real_client_are_ignored(self):
        # The client sent "X-Forwarded-For: 1.2.3.4"; our proxy appended their real IP.
        with mock.patch.object(settings, "TRUSTED_PROXIES", "10.0.0.1"):
            ip = client_ip(self.request("10.0.0.1", "1.2.3.4, 198.51.100.7"))
        self.assertEqual(ip, "198.51.100.7")


if __name__ == "__main__":
    unittest.main()
