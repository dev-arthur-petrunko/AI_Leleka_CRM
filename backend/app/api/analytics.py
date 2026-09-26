"""Дашборд «панель приладів»: KPI, воронка, hot-ліди, прогноз, churn.

Фронт (Recharts/Chart.js) малює графіки з цих endpoints.
Один зведений GET /analytics/dashboard — щоб дашборд вантажився одним запитом.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, require_plan_feature
from app.db.session import get_db
from app.models import Client, Deal
from app.services import ai

# AI-аналітика — платна фіча: Free-тариф отримує 402
router = APIRouter(prefix="/analytics", tags=["analytics"],
                   dependencies=[Depends(require_plan_feature("ai_analytics"))])


@router.get("/kpi")
def kpi(tenant_id: UUID = Depends(get_current_tenant),
        db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=30)
    new_leads = db.query(Client).filter(
        Client.tenant_id == tenant_id, Client.created_at >= since).count()
    total = db.query(Deal).filter(Deal.tenant_id == tenant_id).count() or 1
    won = db.query(Deal).filter(
        Deal.tenant_id == tenant_id, Deal.stage == "won").count()
    avg_check = db.query(func.avg(Deal.amount)).filter(
        Deal.tenant_id == tenant_id, Deal.stage == "won").scalar() or 0
    return {"new_leads_30d": new_leads,
            "conversion": round(won / total, 3),
            "avg_check": round(float(avg_check), 2),
            "won_total": won}


@router.get("/funnel")
def funnel(tenant_id: UUID = Depends(get_current_tenant),
           db: Session = Depends(get_db)):
    rows = db.query(Deal.stage, func.count(Deal.id), func.sum(Deal.amount)).filter(
        Deal.tenant_id == tenant_id).group_by(Deal.stage).all()
    return [{"stage": s, "count": c, "sum": float(sm or 0)} for s, c, sm in rows]


@router.get("/hot-leads")
def hot_leads(tenant_id: UUID = Depends(get_current_tenant),
              db: Session = Depends(get_db)):
    deals = db.query(Deal).filter(
        Deal.tenant_id == tenant_id, Deal.stage.notin_(["won", "lost"])).limit(50).all()
    clients = {str(c.id): c for c in db.query(Client).filter(
        Client.tenant_id == tenant_id).all()}
    scored = [ai.score_deal(d, clients.get(str(d.client_id))) for d in deals]
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:10]


@router.get("/forecast")
def forecast(tenant_id: UUID = Depends(get_current_tenant),
             db: Session = Depends(get_db)):
    won_deals = db.query(Deal).filter(
        Deal.tenant_id == tenant_id, Deal.stage == "won").all()
    by_month: dict[str, float] = defaultdict(float)
    for d in won_deals:
        month = (d.won_at or d.created_at)
        if month:
            by_month[month.strftime("%Y-%m")] += float(d.amount or 0)
    history = [{"month": m, "total": t} for m, t in sorted(by_month.items())]
    return ai.forecast_revenue(history)


@router.get("/churn")
def churn(tenant_id: UUID = Depends(get_current_tenant),
          db: Session = Depends(get_db)):
    return ai.churn_candidates(db, tenant_id)


@router.get("/loss-reasons")
def loss_reasons(tenant_id: UUID = Depends(get_current_tenant),
                 db: Session = Depends(get_db)):
    lost = db.query(Deal.loss_reason).filter(
        Deal.tenant_id == tenant_id, Deal.stage == "lost").all()
    return dict(Counter(r[0] or "невказана" for r in lost))


@router.get("/next-actions")
def next_actions(tenant_id: UUID = Depends(get_current_tenant),
                 db: Session = Depends(get_db)):
    return ai.next_best_actions(db, tenant_id)


@router.get("/dashboard")
def dashboard(tenant_id: UUID = Depends(get_current_tenant),
              db: Session = Depends(get_db)):
    """Один запит для всього дашборду."""
    deals = db.query(Deal).filter(Deal.tenant_id == tenant_id).limit(200).all()
    anon = ai.anonymize_deals(deals)
    return {
        "kpi": kpi(tenant_id, db),
        "funnel": funnel(tenant_id, db),
        "hot_leads": hot_leads(tenant_id, db),
        "forecast": forecast(tenant_id, db),
        "churn": ai.churn_candidates(db, tenant_id),
        "next_actions": ai.next_best_actions(db, tenant_id),
        "ai_insight": ai.ai_text_insight(anon),
    }
