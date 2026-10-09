from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.company import Company
from app.models.user import User, UserRole
from app.models.api_key import ApiKey, ApiKeyStatus
from app.services.api_keys import extract_key_prefix, verify_api_key
from app.services.audit import client_ip, log_action
from app.services.rate_limit import FixedWindowLimiter

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def get_current_member(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """A signed-in user acting inside their company. Every route that touches
    company data depends on this (directly or via require_roles) and filters
    by the returned user's company_id. Platform admins are refused: the
    platform team manages companies and keys but never sees inventory."""
    if current_user.is_platform_admin or current_user.company_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This area is only for company accounts")
    company = db.get(Company, current_user.company_id)
    if company is None or not company.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your company's account has been deactivated")
    return current_user


def require_roles(*roles: str):
    """Company roles allowed on a route. OWNER can always do what ADMIN can,
    so routes only need to name "ADMIN"."""
    allowed = set(roles) | ({UserRole.OWNER.value} if UserRole.ADMIN.value in roles else set())

    def wrapper(current_user: User = Depends(get_current_member)) -> User:
        if current_user.role.value not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        return current_user
    return wrapper


def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the WARE67 platform team can do this")
    return current_user


# last_used_at only needs to be roughly right; writing it on every request
# would turn every partner read into a database write.
LAST_USED_RESOLUTION = timedelta(minutes=5)

# Requests per minute, per API key.
api_key_limiter = FixedWindowLimiter(settings.API_KEY_RATE_LIMIT_PER_MINUTE)
# Failed attempts per minute, per client IP. Only failures count, so a flood of
# bad keys can never lock out a partner sending a valid one from the same IP.
failed_attempt_limiter = FixedWindowLimiter(settings.API_KEY_FAILED_ATTEMPTS_PER_MINUTE)


def _too_many_requests(detail: str, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(retry_after)},
    )


def _reject_api_key(
    db: Session,
    request: Request,
    reason: str,
    *,
    key_prefix: str | None = None,
    api_key: ApiKey | None = None,
    detail: str = "Invalid or missing API key",
) -> HTTPException:
    """Audits a failed attempt and returns the exception to raise. Only the
    public prefix is logged, never the submitted key."""
    retry_after = failed_attempt_limiter.hit(client_ip(request) or "unknown")
    if retry_after is not None:
        return _too_many_requests("Too many failed API key attempts", retry_after)
    # Requests with no key at all are usually crawlers; count them but don't audit.
    if reason != "missing":
        log_action(
            db,
            action="API_KEY_AUTH_FAILED",
            entity="API_KEY",
            entity_id=api_key.id if api_key else None,
            company_id=api_key.company_id if api_key else None,
            details={"reason": reason, "key_prefix": key_prefix},
            request=request,
        )
        db.commit()
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_current_api_key(
    request: Request,
    raw_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> ApiKey:
    if not raw_key:
        raise _reject_api_key(db, request, "missing")

    key_prefix = extract_key_prefix(raw_key)
    if key_prefix is None:
        raise _reject_api_key(db, request, "malformed")

    api_key = db.query(ApiKey).filter(ApiKey.key_prefix == key_prefix).first()
    if api_key is None:
        raise _reject_api_key(db, request, "unknown", key_prefix=key_prefix)
    if not verify_api_key(raw_key, api_key.key_hash):
        raise _reject_api_key(db, request, "bad_secret", key_prefix=key_prefix, api_key=api_key)
    # Revoked and expired are only distinguished after the secret matched, so
    # they reveal nothing to someone who doesn't hold the key. Only revealed
    # keys have a prefix and hash, so anything matched here was once ACTIVE.
    if api_key.status != ApiKeyStatus.ACTIVE:
        raise _reject_api_key(db, request, "revoked", key_prefix=key_prefix, api_key=api_key)
    company = db.get(Company, api_key.company_id)
    if company is None or not company.is_active:
        raise _reject_api_key(db, request, "company_inactive", key_prefix=key_prefix, api_key=api_key)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if api_key.expires_at is not None and api_key.expires_at <= now:
        raise _reject_api_key(
            db, request, "expired",
            key_prefix=key_prefix, api_key=api_key, detail="API key has expired",
        )

    retry_after = api_key_limiter.hit(api_key.id)
    if retry_after is not None:
        raise _too_many_requests("API key rate limit exceeded", retry_after)

    if api_key.last_used_at is None or now - api_key.last_used_at >= LAST_USED_RESOLUTION:
        api_key.last_used_at = now
        db.commit()
    return api_key


def require_api_key_scope(scope: str):
    def wrapper(api_key: ApiKey = Depends(get_current_api_key)) -> ApiKey:
        if scope not in (api_key.scopes or []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key does not have the required scope: {scope}",
            )
        return api_key

    return wrapper
