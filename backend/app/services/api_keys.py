import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey, ApiKeyStatus
from app.services.audit import log_audit

API_KEY_PREFIX = "ware67"
# Hex characters in the public part of the key (48 bits), used to look the key up.
PUBLIC_ID_LENGTH = 12

# Statuses that can still be withdrawn: a request not yet turned into a key,
# or a live key.
REVOCABLE = (ApiKeyStatus.PENDING, ApiKeyStatus.APPROVED, ApiKeyStatus.ACTIVE)


def utcnow() -> datetime:
    """Naive UTC, matching how every other timestamp is stored."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_api_key(raw_key: str) -> str:
    # The secret part is 256 random bits, so a plain SHA-256 can't be brute
    # forced and doesn't tie key validity to any server secret.
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    public_id = secrets.token_hex(PUBLIC_ID_LENGTH // 2)
    key_prefix = f"{API_KEY_PREFIX}_{public_id}"
    raw_key = f"{key_prefix}_{secrets.token_urlsafe(32)}"
    return raw_key, key_prefix, hash_api_key(raw_key)


def generate_unused_key(db: Session) -> tuple[str, str, str]:
    """generate_api_key(), retried in the (very unlikely) case its 48-bit
    public prefix is already taken, instead of failing on the unique index."""
    for _ in range(5):
        raw_key, key_prefix, key_hash = generate_api_key()
        if db.query(ApiKey.id).filter(ApiKey.key_prefix == key_prefix).first() is None:
            return raw_key, key_prefix, key_hash
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not generate a unique API key, try again")


def extract_key_prefix(raw_key: str) -> str | None:
    parts = raw_key.split("_", 2)
    if len(parts) != 3 or parts[0] != API_KEY_PREFIX or len(parts[1]) != PUBLIC_ID_LENGTH:
        return None
    return "_".join(parts[:2])


def verify_api_key(raw_key: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(raw_key), expected_hash)


def effective_status(api_key: ApiKey, now: datetime | None = None) -> str:
    """The status to show. Lapsing and expiring happen with time, not with a
    write, so they're worked out here rather than stored."""
    now = now or utcnow()
    if (api_key.status == ApiKeyStatus.APPROVED and api_key.reveal_deadline is not None
            and api_key.reveal_deadline <= now):
        return ApiKeyStatus.LAPSED.value
    if (api_key.status == ApiKeyStatus.ACTIVE and api_key.expires_at is not None
            and api_key.expires_at <= now):
        return "EXPIRED"
    return api_key.status.value


def to_read(record: ApiKey, schema, /, **extra):
    """Builds a response model with the effective status filled in. extra
    supplies fields the row doesn't have (e.g. company_name, or api_key on
    reveal)."""
    data = {field: getattr(record, field, None) for field in schema.model_fields if field not in extra}
    data["status"] = effective_status(record)
    return schema.model_validate({**data, **extra})


def revoke_key(db: Session, api_key: ApiKey, actor_id: str, request: Request) -> None:
    """Withdraws a request or revokes a live key. Used by both the company and
    the platform team; the caller commits."""
    if api_key.status == ApiKeyStatus.REVOKED:
        raise HTTPException(status.HTTP_409_CONFLICT, "API key is already revoked")
    if api_key.status not in REVOCABLE:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"A {effective_status(api_key).lower()} key can't be revoked")

    previous = api_key.status.value
    api_key.status = ApiKeyStatus.REVOKED
    api_key.revoked_by = actor_id
    api_key.revoked_at = utcnow()
    log_audit(
        db,
        user_id=actor_id,
        action="REVOKE",
        entity="API_KEY",
        entity_id=api_key.id,
        company_id=api_key.company_id,
        details={"name": api_key.name, "key_prefix": api_key.key_prefix, "previous_status": previous},
        request=request,
    )
