"""Трекінг відправлень НП (фаза 3.7): статуси → delivered/returned + автоматизації."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Deal, Order, Shipment


def poll_shipments(db: Session) -> dict:
    from app.core.security import decrypt_credentials
    from app.integrations.novaposhta import NovaPoshtaAdapter
    from app.models import Integration

    done, returned, errors = 0, 0, []
    rows = db.query(Shipment).filter(
        Shipment.carrier == "novaposhta",
        Shipment.delivered_at.is_(None), Shipment.returned_at.is_(None),
        Shipment.ttn.isnot(None)).all()
    for ship in rows:
        try:
            integ = db.query(Integration).filter(
                Integration.tenant_id == ship.tenant_id,
                Integration.provider == "novaposhta").first()
            if not integ:
                continue
            adapter = NovaPoshtaAdapter(decrypt_credentials(integ.credentials),
                                        integ.settings)
            resp = adapter.track(ship.ttn)
            if not resp.get("ok") or resp.get("stub"):
                continue
            data = resp.get("data") or {}
            status = str(data.get("Status") or data.get("status") or "")
            code = str(data.get("StatusCode") or data.get("status_code") or "")
            ship.status, ship.status_code = status, code
            ship.last_polled_at = datetime.now(timezone.utc)
            order = db.query(Order).filter(Order.id == ship.order_id).first()
            if code in ("9", "10", "11") or "вручено" in status.lower() or "отримано" in status.lower():
                ship.delivered_at = datetime.now(timezone.utc)
                if order and order.status != "delivered":
                    order.status = "delivered"
                    _fire(db, ship.tenant_id, order, "order_delivered")
                done += 1
            elif code in ("102", "103", "104", "105") or "відмов" in status.lower() or "поверн" in status.lower():
                ship.returned_at = datetime.now(timezone.utc)
                if order and order.status != "returned":
                    order.status = "returned"
                    _fire(db, ship.tenant_id, order, "order_returned", high=True)
                returned += 1
            db.commit()
        except Exception as e:  # noqa: BLE001
            errors.append(str(e)[:200])
            db.rollback()
    return {"polled": len(rows), "delivered": done, "returned": returned, "errors": errors}


def _fire(db: Session, tenant_id, order: Order, trigger: str, high: bool = False):
    from app.models import Task
    from app.services.automation import run_automations

    run_automations(db, tenant_id, trigger, {
        "order_id": str(order.id), "client_id": str(order.client_id),
        "deal_id": str(order.deal_id) if order.deal_id else None,
        "stage": order.status, "amount": float(order.total or 0)})
    if trigger == "deal_won" and order.deal_id:
        deal = db.query(Deal).filter(Deal.id == order.deal_id).first()
        if deal:
            deal.stage = "won"
    if high:
        db.add(Task(tenant_id=tenant_id, title=f"Повернення по замовленню {order.order_number}",
                    description="Розібрати причину відмови", priority="high"))
    db.commit()
