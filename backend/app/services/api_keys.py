import hashlib
import hmac
import secrets

API_KEY_PREFIX = "ware67"
# Hex characters in the public part of the key (48 bits), used to look the key up.
PUBLIC_ID_LENGTH = 12


def hash_api_key(raw_key: str) -> str:
    # The secret part is 256 random bits, so a plain SHA-256 can't be brute
    # forced and doesn't tie key validity to any server secret.
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    public_id = secrets.token_hex(PUBLIC_ID_LENGTH // 2)
    key_prefix = f"{API_KEY_PREFIX}_{public_id}"
    raw_key = f"{key_prefix}_{secrets.token_urlsafe(32)}"
    return raw_key, key_prefix, hash_api_key(raw_key)


def extract_key_prefix(raw_key: str) -> str | None:
    parts = raw_key.split("_", 2)
    if len(parts) != 3 or parts[0] != API_KEY_PREFIX or len(parts[1]) != PUBLIC_ID_LENGTH:
        return None
    return "_".join(parts[:2])


def verify_api_key(raw_key: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(raw_key), expected_hash)
