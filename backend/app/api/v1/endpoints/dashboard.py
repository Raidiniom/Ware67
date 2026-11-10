from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_member
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.dashboard import DayPoint, InboundDashboard, InboundEvent, TopProduct

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Stock-ins that are not goods arriving. VERIFY against what products.py writes.
EXCLUDED_REFS = ("INITIAL",)


def _db_now(db: Session) -> datetime:
    """Current time on the DB clock, the same clock that stamps created_at."""
    now = db.query(func.now()).scalar()
    if isinstance(now, str):  # SQLite returns text
        now = datetime.fromisoformat(now)
    return now.replace(tzinfo=None)


@router.get("/inbound", response_model=InboundDashboard)
def inbound_dashboard(
    days: int = Query(7, ge=1, le=90),
    recent: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_member),
):
    now = _db_now(db)
    since = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    base = [
        Transaction.company_id == user.company_id,
        Transaction.type == "STOCK_IN",
        Transaction.created_at >= since,
        or_(Transaction.reference_type.is_(None),
            Transaction.reference_type.notin_(EXCLUDED_REFS)),
    ]

    day = func.date(Transaction.created_at)
    per_day = {str(d): (int(u), int(c)) for d, u, c in
               db.query(day, func.sum(Transaction.quantity), func.count(Transaction.id))
                 .filter(*base).group_by(day).all()}
    series = []
    for i in range(days):
        d = (since + timedelta(days=i)).date().isoformat()
        u, c = per_day.get(d, (0, 0))
        series.append(DayPoint(date=d, units=u, transactions=c))

    top = (db.query(Product.id, Product.sku, Product.name, func.sum(Transaction.quantity))
           .join(Transaction, Transaction.product_id == Product.id)
           .filter(*base).group_by(Product.id, Product.sku, Product.name)
           .order_by(func.sum(Transaction.quantity).desc(), Product.id).limit(5).all())

    feed = (db.query(Transaction, Product.name, Product.sku, User.name, ApiKey.name)
            .join(Product, Product.id == Transaction.product_id)
            .outerjoin(User, User.id == Transaction.user_id)
            .outerjoin(ApiKey, ApiKey.id == Transaction.api_key_id)
            .filter(*base)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())  # stable tiebreak
            .limit(recent).all())

    return InboundDashboard(
        days=days,
        units_in=sum(p.units for p in series),
        transactions=sum(p.transactions for p in series),
        series=series,
        top_products=[TopProduct(product_id=i, sku=s, name=n, units=int(u)) for i, s, n, u in top],
        recent=[InboundEvent(id=t.id, created_at=t.created_at, product_name=pn, product_sku=sku,
                             quantity=t.quantity, reference_type=t.reference_type,
                             reference_id=t.reference_id,
                             source=f"API: {kn}" if kn else (un or "—"))
                for t, pn, sku, un, kn in feed],
    )