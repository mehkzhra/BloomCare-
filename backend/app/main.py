import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.account_security import router as account_security_router
from app.admin_api import router as admin_router
from app.api import router
from app.appointment_api import router as appointment_router
from app.assessment_lifecycle import router as assessment_lifecycle_router
from app.care_api import router as care_router
from app.communication_api import router as communication_router
from app.config import get_settings
from app.consultation_api import router as consultation_router
from app.database import SessionLocal, engine
from app.delivery_api import router as delivery_router
from app.extended_api import router as extended_router
from app.family_api import router as family_router
from app.integration_status import router as integration_router
from app.models import AccessAudit
from app.reminders import process_reminders
from app.training_api import router as training_router
from app.workspace_api import router as workspace_router

logger = logging.getLogger("bloomcare")
settings = get_settings()
origins = [item.strip() for item in settings.allowed_origins.split(",") if item.strip()]


@asynccontextmanager
async def lifespan(_app):
    async def worker():
        while True:
            await asyncio.sleep(30)
            try:
                await asyncio.to_thread(process_reminders)
            except Exception:
                logger.warning("Reminder worker could not complete a cycle")

    task = asyncio.create_task(worker())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan, title="BloomCare API", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Report-Title"],
)


def persist_audit(request, status_code):
    # Do not open another failed database connection before returning an outage
    # response, or merely to confirm that an anonymous visitor has no session.
    if getattr(request.state, "database_unavailable", False) or (
        request.url.path == "/api/auth/me"
        and status_code == 401
        and getattr(request.state, "actor_id", None) is None
    ):
        return
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/health/"):
        route = getattr(request.scope.get("route"), "path", "UNMATCHED")
        # Record route templates, never query strings, bodies, tokens or identifiers.
        try:
            with SessionLocal() as db:
                if db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL lock_timeout = '3s'"))
                    db.execute(text("SET LOCAL statement_timeout = '5s'"))
                db.add(
                    AccessAudit(
                        actor_id=getattr(request.state, "actor_id", None),
                        method=request.method,
                        route=route,
                        status_code=status_code,
                    )
                )
                db.commit()
        except Exception:
            logger.warning("Access audit could not be persisted")


@app.middleware("http")
async def response_security(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in origins:
        await asyncio.to_thread(persist_audit, request, 403)
        return JSONResponse(status_code=403, content={"detail": "Origin is not permitted"})
    try:
        response = await call_next(request)
    except Exception:
        await asyncio.to_thread(persist_audit, request, 500)
        raise
    await asyncio.to_thread(persist_audit, request, response.status_code)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
    if settings.cookie_secure and settings.public_app_url.startswith("https://"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["X-Request-ID"] = str(uuid4())
    return response


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeout)
async def database_unavailable(request: Request, _error: Exception):
    request.state.database_unavailable = True
    logger.warning("Database unavailable; type=%s", type(_error).__name__)
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "5"},
        content={
            "detail": ("BloomCare's database is temporarily unavailable. Please try again shortly.")
        },
    )


@app.exception_handler(Exception)
async def unexpected_error(_request: Request, _error: Exception):
    request_id = str(uuid4())
    # Do not log request bodies, tokens, credentials, or medical observations.
    logger.error("Unhandled server error; reference=%s type=%s", request_id, type(_error).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": "The request could not be completed", "reference": request_id},
    )


@app.get("/api/health/live")
def live():
    return {"status": "ok", "version": "1.2.0"}


@app.get("/api/health/ready")
def ready():
    try:
        with engine.connect() as connection:
            for table in (
                "users",
                "account_events",
                "symptom_entries",
                "medication_entries",
                "medical_reports",
                "report_shares",
                "care_messages",
                "notifications",
                "family_grants",
                "medication_reminders",
                "assistant_turns",
                "consultations",
                "consultation_signals",
                "access_audit",
                "appointments",
                "appointment_records",
                "appointment_events",
                "doctor_notes",
                "assessment_care_plans",
                "clinical_reviews",
                "clinical_review_events",
                "follow_up_proposals",
                "whatsapp_alerts",
                "email_action_tokens",
                "auth_rate_buckets",
            ):
                connection.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "database_not_ready"})
    return {"status": "ready"}


app.include_router(family_router)
app.include_router(extended_router)
app.include_router(consultation_router)
app.include_router(communication_router)
app.include_router(care_router)
app.include_router(admin_router)
app.include_router(assessment_lifecycle_router)
app.include_router(router)
app.include_router(appointment_router)
app.include_router(delivery_router)
app.include_router(workspace_router)
app.include_router(training_router)
app.include_router(integration_router)
app.include_router(account_security_router)

if settings.frontend_static_dir:
    from app.web_frontend import mount_frontend

    mount_frontend(app, settings.frontend_static_dir)
