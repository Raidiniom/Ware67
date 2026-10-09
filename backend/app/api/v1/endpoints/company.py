from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_member, require_roles
from app.db.session import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.company import CompanyRead, CompanyRename
from app.services.audit import log_audit

# The signed-in member's own company. There is no id in the path: a member
# can only ever address their own company.
router = APIRouter(prefix="/company", tags=["company"])


@router.get("", response_model=CompanyRead)
def read_my_company(db: Session = Depends(get_db), user: User = Depends(get_current_member)):
    return db.get(Company, user.company_id)


@router.patch("", response_model=CompanyRead)
def rename_my_company(payload: CompanyRename, request: Request,
                      db: Session = Depends(get_db), user: User = Depends(require_roles("OWNER"))):
    company = db.get(Company, user.company_id)
    before = company.name
    company.name = payload.name
    log_audit(db, user_id=user.id, action="UPDATE", entity="COMPANY", entity_id=company.id,
              details={"previous_value": {"name": before}, "new_value": {"name": company.name}},
              request=request)
    db.commit()
    db.refresh(company)
    return company
