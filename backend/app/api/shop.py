"""Аналітика магазину (фаза 6.2): виручка, AOV, LTV, повтори, RFM, повернення."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant
from app.db.session import get_db
from app.models import Client, Deal, Order

router = APIRouter(prefix="/analytics/shop", tags=["shop-analytics"],
                   dependencies=[])


def _paid(q):
    return q.filter(Order.payment_status.in_(["paid", "partial"]))


@router.get("/revenue")
def revenue(tenant_id: UUID = Depends(get_current_tenant),
            db: Session = Depends(get_db),
            days: int = Query(30, le=365)):
    """Виручка і число замовлень по днях (оплачені)."""
    from sqlalchemy import Date, cast

    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.query(cast(Order.placed_at, Date).label("d"),
                    func.sum(Order.total), func.count(Order.id)).filter(
        Order.tenant_id == tenant_id, Order.placed_at >= since)\
        .group_by("d").order_by("d").all()
    paid = _paid(db.query(Order).filter(Order.tenant_id == tenant_id))
    total = paid.with_entities(func.sum(Order.total)).scalar() or 0
    cnt = paid.count()
    return {"by_day": [{"day": str(d), "total": float(t or 0), "count": c}
                       for d, t, c in rows],
            "aov": round(float(total) / cnt, 2) if cnt else 0}


@router.get("/ltv")
def ltv(tenant_id: UUID = Depends(get_current_tenant),
        db: Session = Depends(get_db), limit: int = Query(20, le=100)):
    """LTV топ-клієнтів + частка повторних покупок."""
    sub = db.query(Order.client_id.label("cid"), func.sum(Order.total).label("s"),
                   func.count(Order.id).label("n")).filter(
        Order.tenant_id == tenant_id).group_by(Order.client_id).subquery()
    rows = db.query(Client.name, sub.c.s, sub.c.n).join(
        sub, sub.c.cid == Client.id).order_by(sub.c.s.desc()).limit(limit).all()
    total_clients = db.query(Client).filter(
        Client.tenant_id == tenant_id, Client.deleted_at.is_(None)).count() or 1
    repeaters = db.query(sub.c.cid).filter(sub.c.n >= 2).count()
    return {"top": [{"name": n, "ltv": float(s or 0), "orders": nn} for n, s, nn in rows],
            "repeat_rate": round(repeaters / total_clients, 3)}


@router.get("/rfm")
def rfm(tenant_id: UUID = Depends(get_current_tenant),
        db: Session = Depends(get_db)):
    """RFM-квінтилі через NTILE(5): recency/frequency/monetary по доставлених."""
    from sqlalchemy import text

    rows = db.execute(text(
        "WITH base AS (SELECT client_id, "
        "now()::date - MAX(placed_at)::date AS recency_days, "
        "COUNT(*) AS frequency, SUM(total) AS monetary FROM orders "
        "WHERE tenant_id = :t AND status = 'delivered' GROUP BY client_id) "
        "SELECT client_id, NTILE(5) OVER (ORDER BY recency_days DESC) AS r, "
        "NTILE(5) OVER (ORDER BY frequency) AS f, "
        "NTILE(5) OVER (ORDER BY monetary) AS m FROM base"),
        {"t": str(tenant_id)}).fetchall()
    return [{"client_id": str(r[0]), "r": r[1], "f": r[2], "m": r[3]} for r in rows]


@router.get("/returns")
def returns(tenant_id: UUID = Depends(get_current_tenant),
            db: Session = Depends(get_db)):
    from app.models import Return

    total = db.query(Order).filter(Order.tenant_id == tenant_id).count() or 1
    rets = db.query(Return).filter(Return.tenant_id == tenant_id).all()
    by_reason: dict[str, int] = {}
    for r in rets:
        by_reason[r.reason or "невказана"] = by_reason.get(r.reason or "невказана", 0) + 1
    return {"rate": round(len(rets) / total, 3), "count": len(rets),
            "by_reason": by_reason,
            "lost_revenue": float(sum(float(r.amount or 0) for r in rets))}


@router.get("/forecast-range")
def forecast_range(tenant_id: UUID = Depends(get_current_tenant),
                   db: Session = Depends(get_db)):
    """Чесний прогноз: зважена воронка + ковзне середнє, діапазоном."""
    from app.services import ai as _ai

    open_deals = db.query(Deal).filter(
        Deal.tenant_id == tenant_id, Deal.stage.notin_(["won", "lost"])).all()
    weighted = sum(float(d.amount or 0) * (d.probability or 0) / 100 for d in open_deals)
    won = db.query(Deal).filter(
        Deal.tenant_id == tenant_id, Deal.stage == "won").all()
    by_month: dict[str, float] = {}
    from collections import defaultdict
    by_month = defaultdict(float)
    for d in won:
        m = (d.won_at or d.created_at)
        if m:
            by_month[m.strftime("%Y-%m")] += float(d.amount or 0)
    hist = [{"month": m, "total": t} for m, t in sorted(by_month.items())]
    avg = _ai.forecast_revenue(hist)["forecast_next_month"]
    lo, hi = round(min(weighted, avg), 2), round(max(weighted, avg), 2)
    return {"weighted_pipeline": round(weighted, 2), "moving_avg": avg,
            "range": [lo, hi], "history": hist}
