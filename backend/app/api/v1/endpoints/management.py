from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin, require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User, UserRole
from app.schemas.auth import UserRead
from app.schemas.management import RoleRead, RoleUpdate, UserCreate, UserUpdate
from app.services.audit import log_audit
from app.services.tenancy import get_owned_or_404
from app.services.user_permissions import ensure_can_assign_role, ensure_can_change_user

router = APIRouter(tags=["user-management"])
user_managers = require_roles("ADMIN", "MANAGER")


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
    current_user: User = Depends(user_managers),
):
    users = (db.query(User)
             .filter(User.company_id == current_user.company_id)
             .order_by(User.created_at.desc())
             .all())
    for user in users:
        if user.role_id is None:
            _set_user_role(db, user, user.role.value)
    db.commit()
    return users


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_managed_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(user_managers),
):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    role = _role_value(payload.role)
    ensure_can_assign_role(current_user, role)

    user = User(
        name=payload.name,
        email=email,
        password=hash_password(payload.password),
        is_active=payload.is_active,
        company_id=current_user.company_id,   # always the creator's own company
    )
    db.add(user)
    _set_user_role(db, user, role.value)
    db.flush()                                   # populate user.id
    log_audit(db, user_id=current_user.id, action="CREATE", entity="USER",
              entity_id=user.id, details={"role": role.value, "email": email}, request=request)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_managed_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(user_managers),
):
    user = get_owned_or_404(db, User, user_id, current_user.company_id, "User")

    changes = payload.model_dump(exclude_unset=True)
    requested_role = changes.pop("role", None)
    role = _role_value(requested_role) if requested_role is not None else None
    ensure_can_change_user(current_user, user, role=role, is_active=changes.get("is_active"))
    if role is not None:
        _set_user_role(db, user, role.value)
    if "email" in changes:
        changes["email"] = changes["email"].lower()
        existing = db.query(User).filter(User.email == changes["email"], User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
    if "password" in changes:
        changes["password"] = hash_password(changes["password"])
    for field, value in changes.items():
        setattr(user, field, value)

    log_audit(db, user_id=current_user.id, action="UPDATE", entity="USER", entity_id=user.id,
              details={"changed_fields": sorted(payload.model_dump(exclude_unset=True))},
              request=request)                   # field names only, never the password
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="User could not be updated") from error
    db.refresh(user)
    return user


@router.get("/roles", response_model=list[RoleRead])
def list_roles(
    db: Session = Depends(get_db),
    _current_user: User = Depends(user_managers),
):
    for role in UserRole:
        _get_or_create_role(db, role)
    db.commit()
    return db.query(Role).order_by(Role.name.asc()).all()


# Role descriptions are shown to every company, so only the platform team edits them.
@router.patch("/roles/{role_name}", response_model=RoleRead)
def update_role_description(
    role_name: str,
    payload: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
):
    role = _role_value(role_name)
    record = _get_or_create_role(db, role)
    record.description = payload.description.strip() if payload.description else None
    log_audit(db, user_id=current_user.id, action="UPDATE", entity="ROLE",
              entity_id=record.id, details={"role": role.value}, request=request)
    db.commit()
    db.refresh(record)
    return record
