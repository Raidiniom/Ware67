"""API-level tests for issuing partner API keys and authenticating with them.

Runs the real FastAPI app against an in-memory SQLite database, so no
tunnel or shared MySQL is needed:  python -m unittest discover -s tests
"""
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from starlette.requests import Request

from app.api import deps
from app.core.config import settings
from app.models.api_key import ApiKey
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.models.user import UserRole
from app.services.api_keys import generate_api_key, hash_api_key
from app.services.audit import client_ip
from app.services.rate_limit import FixedWindowLimiter
from support import ApiTestCase, utcnow

PRODUCTS = "/api/v1/integration/products"
API_KEYS = "/api/v1/api-keys"


class ApiKeyTestCase(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.company_id = self.make_company()
        self.owner_id = self.make_user(self.company_id, UserRole.OWNER)
        # Keys are issued by the platform team.
        self.admin_id = self.make_platform_admin()
        self.add(Product(company_id=self.company_id, sku="SKU-1", name="Widget", current_stock=10))

    def admin_auth(self):
        return self.auth(self.admin_id)

    def make_key(self, scopes=("products:read",), **fields):
        """Inserts a key for this test's company and returns (raw_key, key_id)."""
        return super().make_key(self.company_id, self.admin_id, scopes, **fields)

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
        raw_key, _ = self.make_key(is_active=False, revoked_at=utcnow())
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


class ApiKeyIssuingTests(ApiKeyTestCase):
    def create(self, **body):
        return self.client.post(API_KEYS, headers=self.admin_auth(),
                                json={"company_id": self.company_id, "name": "Partner", **body})

    def test_issued_key_works_and_is_stored_as_sha256(self):
        response = self.create(scopes=["products:read"])
        self.assertEqual(response.status_code, 201)
        raw_key = response.json()["api_key"]

        stored = self.get_key(response.json()["id"])
        self.assertEqual(stored.key_hash, hashlib.sha256(raw_key.encode()).hexdigest())
        self.assertEqual(stored.key_hash, hash_api_key(raw_key))
        self.assertEqual(self.client.get(PRODUCTS, headers={"X-API-Key": raw_key}).status_code, 200)

    def test_hash_does_not_depend_on_the_jwt_secret(self):
        raw_key, _, key_hash = generate_api_key()
        with mock.patch.object(settings, "JWT_SECRET_KEY", "rotated-secret"):
            self.assertEqual(hash_api_key(raw_key), key_hash)

    def test_expiry_defaults_to_90_days(self):
        response = self.create()
        expires_at = datetime.fromisoformat(response.json()["expires_at"])
        self.assertAlmostEqual(
            (expires_at - utcnow()).total_seconds(),
            timedelta(days=90).total_seconds(),
            delta=60,
        )

    def test_expiry_within_90_days_is_kept(self):
        wanted = datetime.now(timezone.utc) + timedelta(days=7)
        response = self.create(expires_at=wanted.isoformat())
        self.assertEqual(response.status_code, 201)
        expires_at = datetime.fromisoformat(response.json()["expires_at"])
        self.assertAlmostEqual(
            expires_at.timestamp(), wanted.replace(tzinfo=None).timestamp(), delta=1
        )

    def test_expiry_beyond_90_days_is_rejected(self):
        too_far = datetime.now(timezone.utc) + timedelta(days=91)
        response = self.create(expires_at=too_far.isoformat())
        self.assertEqual(response.status_code, 400)

    def test_expiry_in_the_past_is_rejected(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.assertEqual(self.create(expires_at=past.isoformat()).status_code, 400)

    def test_expiry_without_timezone_is_rejected(self):
        naive = (utcnow() + timedelta(days=7)).isoformat()
        self.assertEqual(self.create(expires_at=naive).status_code, 422)

    def test_issued_prefix_has_12_hex_characters(self):
        prefix = self.create().json()["key_prefix"]
        self.assertRegex(prefix, r"^ware67_[0-9a-f]{12}$")

    def test_prefix_collision_is_retried(self):
        taken_raw, taken_prefix, taken_hash = generate_api_key()
        db = self.Session()
        db.add(ApiKey(company_id=self.company_id, name="Old", key_prefix=taken_prefix,
                      key_hash=taken_hash, scopes=["products:read"], created_by=self.admin_id))
        db.commit()
        db.close()

        fresh = generate_api_key()
        with mock.patch(
            "app.api.v1.endpoints.api_keys.generate_api_key",
            side_effect=[(taken_raw, taken_prefix, taken_hash), fresh],
        ):
            response = self.create()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["key_prefix"], fresh[1])

    def test_revoke_is_audited_and_a_repeat_revoke_conflicts(self):
        _, key_id = self.make_key()
        url = f"{API_KEYS}/{key_id}"
        self.assertEqual(self.client.delete(url, headers=self.admin_auth()).status_code, 204)
        repeat = self.client.delete(url, headers=self.admin_auth())
        self.assertEqual(repeat.status_code, 409)
        self.assertEqual(repeat.json()["detail"], "API key is already revoked")

        db = self.Session()
        revokes = db.query(AuditLog).filter(AuditLog.action == "REVOKE").all()
        db.close()
        self.assertEqual([r.entity_id for r in revokes], [key_id])
        stored = self.get_key(key_id)
        self.assertFalse(stored.is_active)
        self.assertIsNotNone(stored.revoked_at)

    def test_list_is_paginated(self):
        for _ in range(3):
            self.make_key()
        page = self.client.get(API_KEYS, headers=self.admin_auth(), params={"skip": 1, "limit": 2})
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(page.json()), 2)
        self.assertEqual(
            self.client.get(API_KEYS, headers=self.admin_auth(), params={"limit": 500}).status_code,
            422,
        )


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
