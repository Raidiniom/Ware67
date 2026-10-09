from fastapi import Request
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.audit_log import AuditLog


def client_ip(request: Request) -> str | None:
    """The caller's IP. X-Forwarded-For is client-controlled, so it is only
    read when the direct peer is one of settings.TRUSTED_PROXIES."""
    peer = request.client.host if request.client else None
    trusted = settings.trusted_proxies
    if peer is None or peer not in trusted:
        return peer[:45] if peer else None

    # Walk the chain from the nearest hop back; the first address that isn't
    # one of our proxies is the real client. Anything left of it is spoofable.
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    for hop in reversed(hops):
        if hop not in trusted:
            return hop[:45]
    return peer[:45]


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