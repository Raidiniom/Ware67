from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin
from app.core.config import settings
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.company import Company
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services.api_keys import generate_api_key
from app.services.audit import log_audit

# Issuing and revoking keys is the platform team's job, never a company's.
router = APIRouter(prefix="/api-keys", tags=["API keys"])
admin_only = require_platform_admin


def _get_key_or_404(api_key_id: str, db: Session) -> ApiKey:
    api_key = db.get(ApiKey, api_key_id)
    if api_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    return api_key


@router.get("", response_model=list[ApiKeyRead])
def list_api_keys(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    company_id: str | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    query = db.query(ApiKey)
    if company_id:
        query = query.filter(ApiKey.company_id == company_id)
    return (
        query
        .order_by(ApiKey.created_at.desc(), ApiKey.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def _generate_unused_key(db: Session) -> tuple[str, str, str]:
    """generate_api_key(), retried in the (very unlikely) case its 48-bit
    public prefix is already taken, instead of failing on the unique index."""
    for _ in range(5):
        raw_key, key_prefix, key_hash = generate_api_key()
        if db.query(ApiKey.id).filter(ApiKey.key_prefix == key_prefix).first() is None:
            return raw_key, key_prefix, key_hash
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not generate a unique API key, try again")


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    company = db.get(Company, payload.company_id)
    if company is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Company not found")
    if not company.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Company is deactivated")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    max_expires_at = now + timedelta(days=settings.API_KEY_MAX_TTL_DAYS)
    if payload.expires_at is None:
        expires_at = max_expires_at
    else:
        expires_at = payload.expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        if expires_at <= now:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Expiration must be in the future")
        if expires_at > max_expires_at:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Expiration can be at most {settings.API_KEY_MAX_TTL_DAYS} days from now",
            )

    raw_key, key_prefix, key_hash = _generate_unused_key(db)

    api_key = ApiKey(
        company_id=company.id,
        name=payload.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=payload.scopes,
        created_by=admin.id,
        expires_at=expires_at,
    )
    db.add(api_key)
    db.flush()
    log_audit(
        db,
        user_id=admin.id,
        action="CREATE",
        entity="API_KEY",
        entity_id=api_key.id,
        company_id=company.id,   # shows in that company's audit log too
        details={"name": api_key.name, "key_prefix": key_prefix, "scopes": api_key.scopes},
        request=request,
    )
    db.commit()
    db.refresh(api_key)

    result = ApiKeyRead.model_validate(api_key).model_dump()
    return ApiKeyCreated(**result, api_key=raw_key)


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    api_key_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    api_key = _get_key_or_404(api_key_id, db)
    # Say so instead of returning 204 again, so a repeat revoke isn't mistaken
    # for a fresh one that should have appeared in the audit log.
    if not api_key.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "API key is already revoked")

    api_key.is_active = False
    api_key.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    log_audit(
        db,
        user_id=admin.id,
        action="REVOKE",
        entity="API_KEY",
        entity_id=api_key.id,
        company_id=api_key.company_id,
        details={"name": api_key.name, "key_prefix": api_key.key_prefix},
        request=request,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
