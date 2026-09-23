from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User, UserRole
from app.schemas.auth import UserRead
from app.schemas.management import RoleRead, RoleUpdate, UserCreate, UserUpdate
from app.services.audit import log_audit

router = APIRouter(tags=["user-management"])


def _role_value(value: str) -> UserRole:
    try:
        return UserRole(value.upper())
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid role") from error


def _get_or_create_role(db: Session, role: UserRole) -> Role:
    record = db.query(Role).filter(Role.name == role.value).first()
    if record is None:
        record = Role(name=role.value, description=f"{role.value.title()} access")
        db.add(record)
        db.flush()
    return record


def _set_user_role(db: Session, user: User, role_value: str) -> None:
    role = _role_value(role_value)
    role_record = _get_or_create_role(db, role)
    user.role = role
    user.role_id = role_record.id


@router.get("/users", response_model=list[UserRead])
def list_managed_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("ADMIN", "MANAGER")),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    for user in users:
        if user.role_id is None:
            _set_user_role(db, user, user.role.value)
    db.commit()
    return users


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_managed_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "MANAGER")),
):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    role = _role_value(payload.role)
    if current_user.role == UserRole.MANAGER and role in (UserRole.ADMIN, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Managers can only create guest or staff accounts")

    user = User(
        name=payload.name,
        email=email,
        password=hash_password(payload.password),
        is_active=payload.is_active,
    )
    db.add(user)
    _set_user_role(db, user, role.value)
    db.commit()
    db.refresh(user)
    log_audit(db, user_id=current_user.id, action="CREATE", entity="users", entity_id=user.id, details={"role": role.value})
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_managed_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "MANAGER")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    requested_role = changes.get("role")
    if requested_role is not None:
        role = _role_value(requested_role)
        if current_user.role == UserRole.MANAGER and role in (UserRole.ADMIN, UserRole.MANAGER):
            raise HTTPException(status_code=403, detail="Managers cannot assign administrative roles")
        if user.id == current_user.id and role != UserRole.ADMIN:
            raise HTTPException(status_code=400, detail="You cannot remove your own admin access")
        _set_user_role(db, user, role.value)
        changes.pop("role")
    if user.id == current_user.id and changes.get("is_active") is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if "email" in changes:
        changes["email"] = changes["email"].lower()
        existing = db.query(User).filter(User.email == changes["email"], User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
    if "password" in changes:
        changes["password"] = hash_password(changes["password"])
    for field, value in changes.items():
        setattr(user, field, value)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="User could not be updated") from error
    db.refresh(user)
    log_audit(db, user_id=current_user.id, action="UPDATE", entity="users", entity_id=user.id, details={"changed_fields": sorted(payload.model_dump(exclude_unset=True))})
    return user


@router.get("/roles", response_model=list[RoleRead])
def list_roles(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("ADMIN", "MANAGER")),
):
    for role in UserRole:
        _get_or_create_role(db, role)
    db.commit()
    return db.query(Role).order_by(Role.name.asc()).all()


@router.patch("/roles/{role_name}", response_model=RoleRead)
def update_role_description(
    role_name: str,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    role = _role_value(role_name)
    record = _get_or_create_role(db, role)
    record.description = payload.description.strip() if payload.description else None
    db.commit()
    db.refresh(record)
    log_audit(db, user_id=current_user.id, action="UPDATE", entity="roles", entity_id=record.id, details={"role": role.value})
    return record