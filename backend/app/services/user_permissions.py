from fastapi import HTTPException, status

from app.models.user import User, UserRole

PRIVILEGED = (UserRole.ADMIN, UserRole.MANAGER)


def ensure_can_change_user(
    actor: User,
    target: User,
    *,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> None:
    """Single source of truth for who may change another account.
    Every route that edits a user's role or status must call this, so the
    rules cannot drift between /users and the older /auth routes."""
    is_self = actor.id == target.id

    if actor.role == UserRole.MANAGER and not is_self and target.role in PRIVILEGED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Managers cannot modify administrator or manager accounts")

    if role is not None:
        if actor.role == UserRole.MANAGER and role in PRIVILEGED:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Managers cannot assign administrative roles")
        if is_self and role != UserRole.ADMIN:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove your own admin access")

    if is_self and is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")
