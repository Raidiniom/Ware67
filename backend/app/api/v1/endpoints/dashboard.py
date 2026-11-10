from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_member
from app.db.session import get_db
from app.models.product import Product
from app.models.transaction import OPENING_STOCK_REF, Transaction
from app.models.user import User
from app.schemas.dashboard import DayPoint, InboundDashboard, InboundEvent, TopProduct
from app.services.transactions import transaction_rows

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _db_clock(db: Session) -> tuple[datetime, timedelta]:
    """Now (aware, UTC) and how far ahead of UTC the clock that stamps created_at runs.

    created_at is a naive DB-side timestamp: UTC on SQLite (CURRENT_TIMESTAMP),
    the session time zone on MySQL.
    """
    if db.get_bind().dialect.name == "mysql":
        now, ahead = db.execute(text(
            "SELECT UTC_TIMESTAMP(6), TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), NOW())")).one()
        return now.replace(tzinfo=timezone.utc), timedelta(seconds=int(ahead))
    now = db.query(func.now()).scalar()
    if isinstance(now, str):  # SQLite returns text, in UTC
        now = datetime.fromisoformat(now)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc), timedelta(0)
    return now.astimezone(timezone.utc), now.utcoffset()


def _zone(name: str) -> tuple[ZoneInfo, str]:
    """The viewer's zone, or UTC if this server's tz database doesn't know it.

    The response's tz says which one was used, so the page can tell.
    """
    try:
        return ZoneInfo(name), name
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC"), "UTC"


@router.get("/inbound", response_model=InboundDashboard)
def inbound_dashboard(
    days: int = Query(7, ge=1, le=90),
    recent: int = Query(15, ge=1, le=100),
    tz: str = Query("UTC", max_length=64, description="IANA time zone the days are counted in"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_member),
):
    zone, tz = _zone(tz)
    now, ahead = _db_clock(db)

    def to_db(d: date) -> datetime:  # local midnight -> naive DB-clock value
        return (datetime.combine(d, time.min, zone).astimezone(timezone.utc) + ahead).replace(tzinfo=None)

    def to_utc(stamp: datetime | None) -> datetime | None:
        return stamp and (stamp - ahead).replace(tzinfo=timezone.utc)

    today = now.astimezone(zone).date()
    dates = [today - timedelta(days=days - 1 - i) for i in range(days)]
    edges = [to_db(d) for d in dates] + [to_db(today + timedelta(days=1))]

    inbound = [
        Transaction.type == "STOCK_IN",
        Transaction.created_at >= edges[0],
        Transaction.created_at < edges[-1],
        or_(Transaction.reference_type.is_(None),
            Transaction.reference_type != OPENING_STOCK_REF),
    ]
    scoped = [Transaction.company_id == user.company_id, *inbound]

    # Index of the client-local day each row falls on.
    bucket = case(*((Transaction.created_at < e, i) for i, e in enumerate(edges[1:]))).label("bucket")
    per_day = {int(b): (int(u), int(c)) for b, u, c in
               db.query(bucket, func.sum(Transaction.quantity), func.count(Transaction.id))
                 .filter(*scoped).group_by(text("bucket")).all()}
    series = [DayPoint(date=d.isoformat(), units=per_day.get(i, (0, 0))[0],
                       transactions=per_day.get(i, (0, 0))[1])
              for i, d in enumerate(dates)]

    top = (db.query(Product.id, Product.sku, Product.name, func.sum(Transaction.quantity))
           .join(Transaction, Transaction.product_id == Product.id)
           .filter(*scoped).group_by(Product.id, Product.sku, Product.name)
           .order_by(func.sum(Transaction.quantity).desc(), Product.id).limit(5).all())

    feed = (transaction_rows(db, user.company_id).filter(*inbound)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())  # stable tiebreak
            .limit(recent).all())

    return InboundDashboard(
        days=days,
        tz=tz,
        units_in=sum(p.units for p in series),
        transactions=sum(p.transactions for p in series),
        series=series,
        top_products=[TopProduct(product_id=i, sku=s, name=n, units=int(u)) for i, s, n, u in top],
        recent=[InboundEvent(id=t.id, created_at=to_utc(t.created_at), product_name=pn,
                             product_sku=sku, quantity=t.quantity,
                             reference_type=t.reference_type, reference_id=t.reference_id,
                             source=f"API: {kn}" if kn else (un or "—"))
                for t, pn, sku, un, kn in feed],
    )
