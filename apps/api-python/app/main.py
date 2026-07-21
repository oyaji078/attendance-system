from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.api.router import api_router
from app.core.config import get_settings
from app.core.csrf import CsrfProtection, csrf_dependency
from app.core.dependencies import AppContainer
from app.core.logging import configure_logging
from db.models.database import build_engine, build_session_factory
from services.attendance.cache import RedisStateCache
from services.auth_service import AuthService
from services.liveness.service import HeuristicPassiveLivenessService
from services.quality.service import QualityGate
from services.recognition.pipeline import InsightFaceEmbeddingPipeline
from services.recognition.template_builder import TemplateBuilder
from services.storage.object_storage import LocalObjectStorage
from db.repositories.admin_users import AdminUserRepository

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    redis = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    csrf_protection = CsrfProtection(redis, settings.auth_secret_key)
    application.state.container = AppContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        object_storage=LocalObjectStorage(settings.object_storage_root),
        cache=RedisStateCache(redis, settings.heartbeat_ttl_seconds, settings.recent_match_ttl_seconds),
        pipeline=InsightFaceEmbeddingPipeline(settings.insightface_model_name, settings.insightface_model_root, settings.insightface_allowed_providers),
        liveness_service=HeuristicPassiveLivenessService(),
        quality_gate=QualityGate(),
        template_builder=TemplateBuilder(),
        csrf_protection=csrf_protection,
    )
    async with session_factory() as session:
        auth_service = AuthService(AdminUserRepository(session), settings)
        await auth_service.ensure_default_admin()
        await session.commit()
    if settings.recognition_warmup_on_startup:
        warmup_started_at = perf_counter()
        try:
            await application.state.container.pipeline.warmup(
                det_thresh=0.60,
                det_size=(settings.default_detection_size_width, settings.default_detection_size_height),
            )
        except Exception:
            LOGGER.exception("insightface_warmup_failed")
        else:
            LOGGER.info("insightface_warmup_completed", extra={"duration_ms": round((perf_counter() - warmup_started_at) * 1000.0, 2)})
    LOGGER.info("api_started", extra={"app_name": settings.app_name, "app_env": settings.app_env})
    yield
    await redis.aclose()
    await engine.dispose()
    LOGGER.info("api_stopped")


app = FastAPI(title="Campus Face Recognition Attendance System", lifespan=lifespan)

_app_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_app_settings.effective_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "x-csrf-token"],
)
app.include_router(api_router)


def _validation_field(loc: tuple[object, ...]) -> str:
    return ".".join(str(item) for item in loc if item != "body") or "request"


def _validation_message(field: str) -> str:
    if "frame_b64" in field:
        return "Frame kamera tidak valid."
    if "frames" in field:
        return "Jumlah frame tidak sesuai."
    if "session_code" in field:
        return "Kode sesi absensi tidak valid."
    if "device_code" in field:
        return "Kode perangkat tidak valid."
    return "Nilai field tidak valid."


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        field = _validation_field(tuple(error.get("loc", ())))
        errors.append({"field": field, "message": _validation_message(field)})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Permintaan tidak valid.", "errors": errors},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Optionally serve the static kiosk UI from the API itself so a single HTTPS
# tunnel (or reverse proxy) exposes both the page and its API on one origin.
# This keeps camera access (getUserMedia needs a secure context off localhost)
# and admin cookies working without cross-origin CORS/SameSite juggling.
# API routes above are matched first; this mount only catches everything else.
_KIOSK_DIR = Path(__file__).resolve().parents[3] / "apps" / "kiosk-ui" / "src"
if _KIOSK_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_KIOSK_DIR), html=True), name="kiosk")
