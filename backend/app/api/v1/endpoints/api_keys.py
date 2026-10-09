"""Partner API keys: request -> approve -> reveal.

1. A company OWNER/ADMIN requests a key (PENDING). No secret exists yet.
2. The platform team approves it, optionally with fewer scopes (APPROVED), or
   rejects it with a reason (REJECTED). Still no secret.
3. The company reveals it once within the reveal window: only now is the key
   generated, hashed and returned (ACTIVE). The platform team never sees it.

Either side can revoke. The secret is never stored, logged or shown again.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin, require_roles
from app.core.config import settings
from app.db.session import get_db
from app.models.api_key import ApiKey, ApiKeyStatus
from app.models.company import Company
from app.models.user import User
from app.schemas.api_key import (
    ApiKeyApprove,
    ApiKeyList,
    ApiKeyRead,
    ApiKeyReject,
    ApiKeyRequestCreate,
    ApiKeyRevealed,
    PlatformApiKeyList,
    PlatformApiKeyRead,
)
from app.services.api_keys import generate_unused_key, revoke_key, to_read, utcnow
from app.services.audit import log_audit
from app.services.tenancy import get_owned_or_404

# ---------------------------------------------------------------------------
# Company side: OWNER and ADMIN only (require_roles lets OWNER in with ADMIN).
# ---------------------------------------------------------------------------
company_router = APIRouter(prefix="/company/api-keys", tags=["API keys (company)"])
key_managers = require_roles("ADMIN")


def _audit(db: Session, api_key: ApiKey, actor: User, action: str, request: Request, **details) -> None:
    log_audit(db, user_id=actor.id, action=action, entity="API_KEY", entity_id=api_key.id,
              company_id=api_key.company_id,
              details={"name": api_key.name, **details}, request=request)


@company_router.get("", response_model=ApiKeyList)
def list_company_keys(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(key_managers),
):
    q = db.query(ApiKey).filter(ApiKey.company_id == user.company_id)
    total = q.count()
    rows = q.order_by(ApiKey.created_at.desc(), ApiKey.id).offset(skip).limit(limit).all()
    return ApiKeyList(items=[to_read(k, ApiKeyRead) for k in rows], total=total)


@company_router.post("", response_model=ApiKeyRead, status_code=status.HTTP_201_CREATED)
def request_key(payload: ApiKeyRequestCreate, request: Request,
                db: Session = Depends(get_db), user: User = Depends(key_managers)):
    # Cap waiting requests so one company can't flood the platform team's queue.
    now = utcnow()
    open_requests = (
        db.query(ApiKey.id)
        .filter(ApiKey.company_id == user.company_id)
        .filter((ApiKey.status == ApiKeyStatus.PENDING)
                | ((ApiKey.status == ApiKeyStatus.APPROVED) & (ApiKey.reveal_deadline > now)))
        .count()
    )
    if open_requests >= settings.API_KEY_MAX_OPEN_REQUESTS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Your company already has {open_requests} key requests waiting. "
            "Reveal or withdraw one before requesting another.",
        )

    api_key = ApiKey(
        company_id=user.company_id,
        name=payload.name,
        purpose=payload.purpose,
        status=ApiKeyStatus.PENDING,
        requested_scopes=payload.scopes,
        requested_by=user.id,
    )
    db.add(api_key)
    db.flush()
    _audit(db, api_key, user, "REQUEST", request, scopes=payload.scopes)
    db.commit()
    db.refresh(api_key)
    return to_read(api_key, ApiKeyRead)


REVEAL_REFUSALS = {
    ApiKeyStatus.PENDING: "This request is still waiting for approval by the WARE67 team",
    ApiKeyStatus.REJECTED: "This request was rejected",
    ApiKeyStatus.REVOKED: "This key was revoked",
    ApiKeyStatus.LAPSED: "This approval lapsed before the key was revealed. Request a new key.",
    ApiKeyStatus.ACTIVE: "This key was already revealed and can't be shown again. "
                         "If it's lost, revoke it and request a new one.",
}


@company_router.post("/{api_key_id}/reveal", response_model=ApiKeyRevealed)
def reveal_key(api_key_id: str, request: Request,
               db: Session = Depends(get_db), user: User = Depends(key_managers)):
    # Lock the row so two clicks at once can't both generate a key.
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.id == api_key_id, ApiKey.company_id == user.company_id)
        .with_for_update()
        .one_or_none()
    )
    if api_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")

    now = utcnow()
    if api_key.status == ApiKeyStatus.APPROVED and api_key.reveal_deadline <= now:
        api_key.status = ApiKeyStatus.LAPSED
        _audit(db, api_key, user, "LAPSE", request)
        db.commit()
    if api_key.status != ApiKeyStatus.APPROVED:
        raise HTTPException(status.HTTP_409_CONFLICT, REVEAL_REFUSALS[api_key.status])

    raw_key, key_prefix, key_hash = generate_unused_key(db)
    api_key.key_prefix = key_prefix
    api_key.key_hash = key_hash
    api_key.status = ApiKeyStatus.ACTIVE
    api_key.revealed_by = user.id
    api_key.revealed_at = now
    api_key.expires_at = now + timedelta(days=settings.API_KEY_MAX_TTL_DAYS)
    _audit(db, api_key, user, "REVEAL", request, key_prefix=key_prefix,
           scopes=api_key.scopes, expires_at=api_key.expires_at.isoformat())
    db.commit()
    db.refresh(api_key)
    return to_read(api_key, ApiKeyRevealed, api_key=raw_key)


@company_router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_company_key(api_key_id: str, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(key_managers)):
    """Withdraw a request, or revoke a live key (e.g. if it leaked)."""
    api_key = get_owned_or_404(db, ApiKey, api_key_id, user.company_id, "API key")
    revoke_key(db, api_key, user.id, request)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Platform side: the WARE67 team reviews requests and can revoke any key.
# ---------------------------------------------------------------------------
platform_router = APIRouter(prefix="/platform/api-keys", tags=["API keys (platform)"])


def _platform_query(db: Session):
    return db.query(ApiKey, Company.name).join(Company, Company.id == ApiKey.company_id)


def _platform_read(row) -> PlatformApiKeyRead:
    api_key, company_name = row
    return to_read(api_key, PlatformApiKeyRead, company_name=company_name)


def _get_for_platform_or_404(db: Session, api_key_id: str, *, lock: bool = False) -> ApiKey:
    q = db.query(ApiKey).filter(ApiKey.id == api_key_id)
    if lock:
        q = q.with_for_update()
    api_key = q.one_or_none()
    if api_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    return api_key


def _ensure_pending(api_key: ApiKey) -> None:
    if api_key.status != ApiKeyStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Only pending requests can be reviewed; this one is {api_key.status.value}")


@platform_router.get("", response_model=PlatformApiKeyList)
def list_all_keys(
    status_filter: ApiKeyStatus | None = Query(None, alias="status"),
    company_id: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_platform_admin),
):
    """status=PENDING is the review queue (oldest first)."""
    q = _platform_query(db)
    if status_filter is not None:
        q = q.filter(ApiKey.status == status_filter)
    if company_id:
        q = q.filter(ApiKey.company_id == company_id)
    order = ApiKey.created_at.asc() if status_filter == ApiKeyStatus.PENDING else ApiKey.created_at.desc()
    total = q.count()
    rows = q.order_by(order, ApiKey.id).offset(skip).limit(limit).all()
    return PlatformApiKeyList(items=[_platform_read(r) for r in rows], total=total)


# Declared before "/{api_key_id}" so "expiring" isn't treated as an id.
@platform_router.get("/expiring", response_model=PlatformApiKeyList)
def list_expiring_keys(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_platform_admin),
):
    """Live keys that stop working within the next `days` days, soonest first,
    so the team can remind companies to request a replacement."""
    now = utcnow()
    q = (_platform_query(db)
         .filter(ApiKey.status == ApiKeyStatus.ACTIVE,
                 ApiKey.expires_at > now,
                 ApiKey.expires_at <= now + timedelta(days=days)))
    rows = q.order_by(ApiKey.expires_at.asc(), ApiKey.id).all()
    return PlatformApiKeyList(items=[_platform_read(r) for r in rows], total=len(rows))


def _read_one(db: Session, api_key_id: str) -> PlatformApiKeyRead:
    row = _platform_query(db).filter(ApiKey.id == api_key_id).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    return _platform_read(row)


@platform_router.get("/{api_key_id}", response_model=PlatformApiKeyRead)
def get_key(api_key_id: str, db: Session = Depends(get_db),
            _admin: User = Depends(require_platform_admin)):
    return _read_one(db, api_key_id)


@platform_router.post("/{api_key_id}/approve", response_model=PlatformApiKeyRead)
def approve_key(api_key_id: str, payload: ApiKeyApprove, request: Request,
                db: Session = Depends(get_db), admin: User = Depends(require_platform_admin)):
    api_key = _get_for_platform_or_404(db, api_key_id, lock=True)
    _ensure_pending(api_key)
    company = db.get(Company, api_key.company_id)
    if not company.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "The company is deactivated")

    granted = payload.scopes or list(api_key.requested_scopes)
    extra = set(granted) - set(api_key.requested_scopes)
    if extra:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Can only grant scopes the company asked for, not: {', '.join(sorted(extra))}")

    now = utcnow()
    api_key.status = ApiKeyStatus.APPROVED
    api_key.scopes = granted
    api_key.reviewed_by = admin.id
    api_key.reviewed_at = now
    api_key.reveal_deadline = now + timedelta(days=settings.API_KEY_REVEAL_WINDOW_DAYS)
    _audit(db, api_key, admin, "APPROVE", request,
           requested_scopes=api_key.requested_scopes, granted_scopes=granted)
    db.commit()
    return _read_one(db, api_key.id)


@platform_router.post("/{api_key_id}/reject", response_model=PlatformApiKeyRead)
def reject_key(api_key_id: str, payload: ApiKeyReject, request: Request,
               db: Session = Depends(get_db), admin: User = Depends(require_platform_admin)):
    api_key = _get_for_platform_or_404(db, api_key_id, lock=True)
    _ensure_pending(api_key)
    api_key.status = ApiKeyStatus.REJECTED
    api_key.reviewed_by = admin.id
    api_key.reviewed_at = utcnow()
    api_key.rejection_reason = payload.reason
    _audit(db, api_key, admin, "REJECT", request, reason=payload.reason)
    db.commit()
    return _read_one(db, api_key.id)


@platform_router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_any_key(api_key_id: str, request: Request,
                   db: Session = Depends(get_db), admin: User = Depends(require_platform_admin)):
    api_key = _get_for_platform_or_404(db, api_key_id)
    revoke_key(db, api_key, admin.id, request)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
