from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.models.api_key import ApiKey
from app.services.api_keys import extract_key_prefix, verify_api_key

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


def require_roles(*roles: str):
    def wrapper(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.value not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        return current_user
    return wrapper


def get_current_api_key(
    raw_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> ApiKey:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )
    if not raw_key:
        raise credentials_exception

    key_prefix = extract_key_prefix(raw_key)
    if key_prefix is None:
        raise credentials_exception

    api_key = db.query(ApiKey).filter(ApiKey.key_prefix == key_prefix).first()
    if api_key is None or not api_key.is_active:
        raise credentials_exception
    if not verify_api_key(raw_key, api_key.key_hash):
        raise credentials_exception

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if api_key.expires_at is not None and api_key.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    api_key.last_used_at = now
    db.commit()
    db.refresh(api_key)
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
