from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from jose import JWTError

from app.api.deps import get_current_user, require_roles
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User, UserRole
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    OnboardRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UpdateRoleRequest,
    UpdateStatusRequest,
    UserRead,
)
from app.services.audit import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])

# Same entity name the rest of the app uses (see management.py), so the
# audit-log "entity" filter works for auth events too.
ENTITY = "USER"


def _ensure_role_record(db: Session, role: UserRole) -> Role:
    record = db.query(Role).filter(Role.name == role.value).first()
    if record is None:
        record = Role(name=role.value, description=f"{role.value.title()} access")
        db.add(record)
        db.flush()
    return record


# NOTE ON AUDIT LOGGING
# log_audit() only *adds* a row to the session; it never commits. Every call
# below therefore happens BEFORE the endpoint's db.commit(), so the audit row
# is saved atomically with the change it describes. (Previously the calls ran
# after the commit, so the rows were silently discarded when the session
# closed.) For error paths we commit explicitly before raising, because
# get_db() rolls the session back when an exception escapes.


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    user = User(
        name=payload.name.strip(),
        email=payload.email.lower(),
        password=hash_password(payload.password),
        role=UserRole.GUEST,
    )
    user.role_id = _ensure_role_record(db, UserRole.GUEST).id
    db.add(user)
    db.flush()  # populate user.id for the audit row

    log_audit(
        db,
        user_id=user.id,
        action="REGISTER",
        entity=ENTITY,
        entity_id=user.id,
        details={"email": user.email, "role": user.role.value},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()

    if not user or not verify_password(payload.password, user.password):
        log_audit(
            db,
            user_id=None,
            action="LOGIN_FAILED",
            entity=ENTITY,
            entity_id=user.id if user else None,
            details={"email": payload.email.lower()},
            request=request,
        )
        db.commit()  # commit before raising, otherwise get_db() rolls it back
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )

    log_audit(
        db,
        user_id=user.id,
        action="LOGIN",
        entity=ENTITY,
        entity_id=user.id,
        details={"email": user.email, "role": user.role.value},
        request=request,
    )
    db.commit()

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
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="We couldn't find an active account with that email.",
        )

    user.password = hash_password(payload.new_password)
    log_audit(
        db,
        user_id=user.id,
        action="FORGOT_PASSWORD",
        entity=ENTITY,
        entity_id=user.id,
        details={"email": user.email},
        request=request,
    )
    db.commit()

    return MessageResponse(message="Your password has been changed. You can now log in with your new password.")


@router.post("/onboard", response_model=UserRead)
def onboard(
    payload: OnboardRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "MANAGER")),
):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_role = user.role.value

    try:
        new_role = UserRole(payload.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    user.role = new_role
    user.role_id = _ensure_role_record(db, new_role).id
    user.is_active = payload.is_active

    log_audit(
        db,
        user_id=current_user.id,
        action="ONBOARD",
        entity=ENTITY,
        entity_id=user.id,
        details={"old_role": old_role, "new_role": new_role.value, "is_active": user.is_active},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/update-role", response_model=UserRead)
def update_role(
    payload: UpdateRoleRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        new_role = UserRole(payload.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    old_role = user.role.value
    user.role = new_role
    user.role_id = _ensure_role_record(db, new_role).id

    log_audit(
        db,
        user_id=current_user.id,
        action="UPDATE_ROLE",
        entity=ENTITY,
        entity_id=user.id,
        details={"old_role": old_role, "new_role": new_role.value},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/update-status", response_model=UserRead)
def update_status(
    payload: UpdateStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "MANAGER")),
):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = payload.is_active

    log_audit(
        db,
        user_id=current_user.id,
        action="UPDATE_STATUS",
        entity=ENTITY,
        entity_id=user.id,
        details={"is_active": user.is_active},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return user