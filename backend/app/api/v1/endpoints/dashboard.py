from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_member
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.dashboard import DayPoint, InboundDashboard, InboundEvent, TopProduct

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/inbound", response_model=InboundDashboard)
def inbound_dashboard(
    days: int = Query(7, ge=1, le=90),
    recent: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_member),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    base = [Transaction.company_id == user.company_id,
            Transaction.type == "STOCK_IN",
            Transaction.created_at >= since]

    units, count = db.query(func.coalesce(func.sum(Transaction.quantity), 0),
                            func.count(Transaction.id)).filter(*base).one()

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
           .order_by(func.sum(Transaction.quantity).desc()).limit(5).all())

    feed = (db.query(Transaction, Product.name, Product.sku, User.name, ApiKey.name)
            .join(Product, Product.id == Transaction.product_id)
            .outerjoin(User, User.id == Transaction.user_id)
            .outerjoin(ApiKey, ApiKey.id == Transaction.api_key_id)
            .filter(*base).order_by(Transaction.created_at.desc()).limit(recent).all())

    return InboundDashboard(
        days=days, units_in=int(units), transactions=int(count), series=series,
        top_products=[TopProduct(product_id=i, sku=s, name=n, units=int(u)) for i, s, n, u in top],
        recent=[InboundEvent(id=t.id, created_at=t.created_at, product_name=pn, product_sku=sku,
                             quantity=t.quantity, reference_type=t.reference_type,
                             reference_id=t.reference_id,
                             source=f"API: {kn}" if kn else (un or "—"))
                for t, pn, sku, un, kn in feed],
    )
