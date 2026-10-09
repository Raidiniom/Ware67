from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogList, AuditLogRead

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])
admin_only = require_roles("ADMIN")
# GET only on purpose: audit logs have no create/update/delete endpoints.


def _read(log: AuditLog, uname, uemail) -> AuditLogRead:
    r = AuditLogRead.model_validate(log)
    r.user_name, r.user_email = uname, uemail
    return r


def base_query(db: Session, scope):
    """scope is a filter clause choosing which rows the caller may see: one
    company's, or the platform's."""
    # outer join: user_id becomes NULL when a user is deleted, and the row must survive
    return (db.query(AuditLog, User.name, User.email)
            .outerjoin(User, User.id == AuditLog.user_id)
            .filter(scope))


def list_logs(q, *, search, user_id, action, entity, entity_id, date_from, date_to,
              skip, limit) -> AuditLogList:
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(or_(AuditLog.action.like(like), AuditLog.entity.like(like),
                         AuditLog.entity_id.like(like), AuditLog.ip_address.like(like),
                         User.name.like(like), User.email.like(like)))
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action == action.upper())
    if entity:
        q = q.filter(AuditLog.entity == entity.upper())
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if date_from:
        q = q.filter(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        q = q.filter(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min))

    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
    return AuditLogList(items=[_read(*r) for r in rows], total=total)


def get_log_or_404(q, log_id: str) -> AuditLogRead:
    row = q.filter(AuditLog.id == log_id).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit log not found")
    return _read(*row)


@router.get("", response_model=AuditLogList)
def list_audit_logs(
    search: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    entity: str | None = None,
    entity_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(admin_only),
):
    return list_logs(
        base_query(db, AuditLog.company_id == user.company_id),
        search=search, user_id=user_id, action=action, entity=entity, entity_id=entity_id,
        date_from=date_from, date_to=date_to, skip=skip, limit=limit,
    )


@router.get("/{log_id}", response_model=AuditLogRead)
def get_audit_log(log_id: str, db: Session = Depends(get_db), user: User = Depends(admin_only)):
    return get_log_or_404(base_query(db, AuditLog.company_id == user.company_id), log_id)
