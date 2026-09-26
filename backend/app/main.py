from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.api import (
    analytics,
    auth,
    automations,
    billing,
    clients,
    deals,
    integrations,
    notifications,
    tasks,
    webhooks,
)
from app.core.config import frontend_origins
from app.core.rate import limiter
from app.db.session import Base, engine

# Імпорт моделей щоб create_all побачив таблиці
import app.models  # noqa: F401

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(title="AI Leleka CRM", version="0.1.0-mvp")
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda req, exc: JSONResponse(status_code=429, content={"detail": "Забагато запитів, спробуйте пізніше"}),
)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(deals.router)
app.include_router(tasks.router)
app.include_router(webhooks.router)
app.include_router(automations.router)
app.include_router(analytics.router)
app.include_router(billing.router)
app.include_router(integrations.router)
app.include_router(notifications.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)  # MVP; далі — Alembic (backend/alembic/)


@app.get("/health")
def health():
    return {"ok": True, "service": "ai-leleka-crm"}
