import hashlib
import hmac
import secrets

from app.core.config import settings

API_KEY_PREFIX = "ware67"


def hash_api_key(raw_key: str) -> str:
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        raw_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    public_id = secrets.token_hex(4)
    key_prefix = f"{API_KEY_PREFIX}_{public_id}"
    raw_key = f"{key_prefix}_{secrets.token_urlsafe(32)}"
    return raw_key, key_prefix, hash_api_key(raw_key)


def extract_key_prefix(raw_key: str) -> str | None:
    parts = raw_key.split("_", 2)
    if len(parts) != 3 or parts[0] != API_KEY_PREFIX or len(parts[1]) != 8:
        return None
    return "_".join(parts[:2])


def verify_api_key(raw_key: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(raw_key), expected_hash)
