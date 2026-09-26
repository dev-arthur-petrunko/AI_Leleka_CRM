from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
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
    """Схему більше не створює create_all() — нею володіє Alembic.

    Перед стартом контейнера виконати: alembic upgrade head
    (docker-compose command вже робить це, див. docker-compose.yml).
    Тут лише перевіряємо, що з'єднання з БД справді живе, щоб
    контейнер одразу впав з зрозумілою помилкою, а не на першому запиті.
    """
    from sqlalchemy import text

    from app.db.session import engine

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


@app.get("/health")
def health():
    return {"ok": True, "service": "ai-leleka-crm"}
