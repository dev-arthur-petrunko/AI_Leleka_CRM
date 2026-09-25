from fastapi import FastAPI

from app.api import auth, automations, clients, deals, tasks, webhooks
from app.db.session import Base, engine

# Импорт моделей чтобы create_all увидел таблицы
import app.models  # noqa: F401

app = FastAPI(title="AI Leleka CRM", version="0.1.0-mvp")

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(deals.router)
app.include_router(tasks.router)
app.include_router(webhooks.router)
app.include_router(automations.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)  # MVP; в проде — Alembic


@app.get("/health")
def health():
    return {"ok": True, "service": "ai-leleka-crm"}
