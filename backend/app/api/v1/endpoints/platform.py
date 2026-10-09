"""Routes for the WARE67 platform team. They manage companies (and API keys,
see api_keys.py) but deliberately have no route into any company's inventory."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin
from app.api.v1.endpoints.audit_logs import base_query, get_log_or_404, list_logs
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.user import User
from app.schemas.audit import AuditLogList, AuditLogRead
from app.schemas.company import PlatformCompanyList, PlatformCompanyRead, PlatformCompanyUpdate
from app.services.audit import log_audit

router = APIRouter(prefix="/platform", tags=["platform"])

# What the platform audit log shows: platform-level events, plus company and
# API key events. Not product, stock or user activity inside companies.
PLATFORM_AUDIT_SCOPE = or_(
    AuditLog.company_id.is_(None),
    AuditLog.entity.in_(("COMPANY", "API_KEY")),
)


def _member_count(db: Session, company_id: str) -> int:
    return db.query(func.count(User.id)).filter(User.company_id == company_id).scalar()


def _to_read(company: Company, members: int) -> PlatformCompanyRead:
    r = PlatformCompanyRead.model_validate(company)
    r.member_count = members
    return r


def _get_company_or_404(db: Session, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    return company


@router.get("/companies", response_model=PlatformCompanyList)
def list_companies(
    search: str | None = None,
    is_active: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_platform_admin),
):
    members = func.count(User.id).label("member_count")
    q = (db.query(Company, members)
         .outerjoin(User, User.company_id == Company.id)
         .group_by(Company.id))
    if search:
        q = q.filter(Company.name.like(f"%{search.strip()}%"))
    if is_active is not None:
        q = q.filter(Company.is_active.is_(is_active))
    total = q.count()
    rows = q.order_by(Company.created_at.desc(), Company.id).offset(skip).limit(limit).all()
    return PlatformCompanyList(items=[_to_read(c, n) for c, n in rows], total=total)


@router.get("/companies/{company_id}", response_model=PlatformCompanyRead)
def get_company(company_id: str, db: Session = Depends(get_db),
                _admin: User = Depends(require_platform_admin)):
    company = _get_company_or_404(db, company_id)
    return _to_read(company, _member_count(db, company.id))


@router.patch("/companies/{company_id}", response_model=PlatformCompanyRead)
def update_company(company_id: str, payload: PlatformCompanyUpdate, request: Request,
                   db: Session = Depends(get_db),
                   admin: User = Depends(require_platform_admin)):
    """Rename, or deactivate/reactivate a company. A deactivated company's
    members can't sign in and its API keys stop working immediately."""
    company = _get_company_or_404(db, company_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    before = {field: getattr(company, field) for field in changes}
    for field, value in changes.items():
        setattr(company, field, value)
    log_audit(db, user_id=admin.id, action="UPDATE", entity="COMPANY", entity_id=company.id,
              company_id=company.id,
              details={"previous_value": before, "new_value": changes}, request=request)
    db.commit()
    db.refresh(company)
    return _to_read(company, _member_count(db, company.id))


@router.get("/audit-logs", response_model=AuditLogList)
def list_platform_audit_logs(
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
    _admin: User = Depends(require_platform_admin),
):
    return list_logs(
        base_query(db, PLATFORM_AUDIT_SCOPE),
        search=search, user_id=user_id, action=action, entity=entity, entity_id=entity_id,
        date_from=date_from, date_to=date_to, skip=skip, limit=limit,
    )


@router.get("/audit-logs/{log_id}", response_model=AuditLogRead)
def get_platform_audit_log(log_id: str, db: Session = Depends(get_db),
                           _admin: User = Depends(require_platform_admin)):
    return get_log_or_404(base_query(db, PLATFORM_AUDIT_SCOPE), log_id)
