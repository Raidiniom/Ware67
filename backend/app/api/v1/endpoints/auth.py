from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserRead,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    user = User(
        name=payload.name,
        email=payload.email,
        password=hash_password(payload.password),
        role=UserRole.STAFF,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )

    return TokenPair(
        access_token=create_access_token(user_id=user.id, role=user.role.value),
        refresh_token=create_refresh_token(user_id=user.id),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    try:
        token_payload = decode_token(payload.refresh_token)
        if token_payload.get("type") != "refresh":
            raise credentials_exception
        user_id = token_payload.get("sub")
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return TokenPair(
        access_token=create_access_token(user_id=user.id, role=user.role.value),
        refresh_token=create_refresh_token(user_id=user.id),
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    # No email/SMS provider available on this host, so there's no reset
    # link — the account is verified with email + full name, then the
    # password is changed immediately.
    #
    # NOTE: this is a much weaker check than a real "forgot password" flow
    # (anyone who knows a user's email + name can change their password —
    # both are often not-very-secret in a small org). It's a reasonable
    # trade-off given no outbound email is available, but if that changes
    # later, prefer swapping this for an emailed, single-use reset link.
    verification_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="We couldn't verify those account details. Double-check your email and full name.",
    )

    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.is_active:
        raise verification_error

    if user.name.strip().lower() != payload.name.strip().lower():
        raise verification_error

    user.password = hash_password(payload.new_password)
    db.commit()

    return MessageResponse(message="Your password has been changed. You can now log in with your new password.")
