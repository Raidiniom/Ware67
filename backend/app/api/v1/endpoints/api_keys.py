from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services.api_keys import generate_api_key
from app.services.audit import log_audit

router = APIRouter(prefix="/api-keys", tags=["API keys"])
admin_only = require_roles("ADMIN")


def _get_key_or_404(api_key_id: str, db: Session) -> ApiKey:
    api_key = db.get(ApiKey, api_key_id)
    if api_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    return api_key


@router.get("", response_model=list[ApiKeyRead])
def list_api_keys(
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    return db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_only),
):
    raw_key, key_prefix, key_hash = generate_api_key()
    expires_at = payload.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        if expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Expiration must be in the future")

    api_key = ApiKey(
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
    if api_key.is_active:
        api_key.is_active = False
        api_key.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        log_audit(
            db,
            user_id=admin.id,
            action="REVOKE",
            entity="API_KEY",
            entity_id=api_key.id,
            details={"name": api_key.name, "key_prefix": api_key.key_prefix},
            request=request,
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
