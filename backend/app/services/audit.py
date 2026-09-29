from fastapi import Request
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:45]
    return request.client.host if request.client else None


def log_action(db: Session, *, user_id=None, action, entity, entity_id=None,
               details=None, request: Request | None = None) -> None:
    """Adds an audit row to the caller's session. Does NOT commit, so the
    audit entry is atomic with the change it describes."""
    db.add(AuditLog(
        user_id=user_id, action=action, entity=entity, entity_id=entity_id,
        details=details, ip_address=client_ip(request) if request else None,
    ))


def log_audit(db: Session, action: str | None = None, entity: str | None = None,
              entity_id=None, details=None, request: Request | None = None,
              user=None, user_id=None, **kwargs) -> None:
    """Compatibility wrapper: accepts either `user=<User>` or `user_id=<str>`,
    and positional or keyword action/entity."""
    if user_id is None and user is not None:
        user_id = getattr(user, "id", user)
    log_action(
        db,
        user_id=user_id,
        action=action or kwargs.pop("event", None),
        entity=entity or kwargs.pop("entity_type", None),
        entity_id=entity_id,
        details=details,
        request=request,
    )