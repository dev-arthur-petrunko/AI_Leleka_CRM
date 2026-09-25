"""Монетизація за KeepinCRM (п.7 плану).

- Free: 1 користувач, без AI, без маркетплейсів — замануха для малого бізнесу
- Pro 350 грн/міс за місце: +AI + Prom/Rozetka + НП
- Team 300 грн/міс за місце (від 5): +Checkbox/РРО + пріоритет
- Платні модулі: ai_analytics, marketplace, fiscal — можна докупити окремо
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Tenant, User

PLANS = {
    "free": {"seats": 1, "price_uah": 0,
             "features": [],
             "label": "Free — 1 користувач"},
    "pro": {"seats": 5, "price_uah": 350,
            "features": ["ai_analytics", "marketplace", "novaposhta"],
            "label": "Pro — 350 грн/міс за місце"},
    "team": {"seats": 10, "price_uah": 300,
             "features": ["ai_analytics", "marketplace", "novaposhta",
                          "fiscal", "priority_support"],
             "label": "Team — 300 грн/міс за місце (5+)"},
}


def current_plan(tenant: Tenant) -> dict:
    return PLANS.get(tenant.plan, PLANS["free"])


def require_feature(tenant: Tenant, feature: str):
    if feature not in current_plan(tenant)["features"]:
        raise HTTPException(
            402, f"Потрібен платний план для '{feature}'. "
                 f"Поточний: {tenant.plan}. POST /billing/upgrade")


def check_seats(db: Session, tenant_id: UUID):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    seats = db.query(User).filter(
        User.tenant_id == tenant_id, User.is_active.is_(True)).count()
    limit = current_plan(tenant)["seats"]
    if seats >= limit:
        raise HTTPException(
            402, f"Ліміт місць вичерпано ({seats}/{limit} на {tenant.plan}). "
                 f"Докупіть місце або апгрейд: POST /billing/upgrade")
