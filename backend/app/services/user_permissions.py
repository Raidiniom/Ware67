from fastapi import HTTPException, status

from app.models.user import User, UserRole

RANK = {
    UserRole.GUEST: 0,
    UserRole.STAFF: 1,
    UserRole.MANAGER: 2,
    UserRole.ADMIN: 3,
    UserRole.OWNER: 4,
}


def ensure_can_assign_role(actor: User, role: UserRole) -> None:
    """Owners may hand out any role, admins any role but owner, managers only
    staff and guest. Used both when creating and when changing an account."""
    if actor.role == UserRole.OWNER:
        return
    if actor.role == UserRole.ADMIN and role != UserRole.OWNER:
        return
    if actor.role == UserRole.MANAGER and role in (UserRole.GUEST, UserRole.STAFF):
        return
    if actor.role == UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners can assign the owner role")
    if actor.role == UserRole.MANAGER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Managers cannot assign administrative roles")
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not enough permissions")


def ensure_can_change_user(
    actor: User,
    target: User,
    *,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> None:
    """Single source of truth for who may change another account.
    Every route that edits a user's role or status must call this, so the
    rules cannot drift between /users and the older /auth routes.

    Together these rules keep every company with an active owner: only owners
    can touch owners, and nobody can demote or deactivate themselves, so an
    owner can only be demoted by another owner who stays behind."""
    # Callers look target up within the actor's company already; this is the
    # backstop, and it says "not found" so ids can't be probed.
    if actor.company_id is None or actor.company_id != target.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    is_self = actor.id == target.id
    if not is_self:
        if actor.role == UserRole.MANAGER and target.role not in (UserRole.GUEST, UserRole.STAFF):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Managers cannot modify administrator or manager accounts")
        if actor.role == UserRole.ADMIN and target.role == UserRole.OWNER:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners can modify owner accounts")

    if role is not None:
        ensure_can_assign_role(actor, role)
        if is_self and RANK[role] < RANK[actor.role]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot lower your own role")

    if is_self and is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")
