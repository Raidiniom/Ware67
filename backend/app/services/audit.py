from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_audit(db: Session, *, user_id: str | None, action: str, entity: str, entity_id: str | None = None, details: dict | None = None, ip_address: str | None = None) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
