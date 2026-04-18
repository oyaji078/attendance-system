from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.router import api_router
from app.core.config import get_settings
from app.core.dependencies import AppContainer
from app.core.logging import configure_logging
from db.models.database import build_engine, build_session_factory
from services.attendance.cache import RedisStateCache
from services.liveness.service import HeuristicPassiveLivenessService
from services.quality.service import QualityGate
from services.recognition.pipeline import InsightFaceEmbeddingPipeline
from services.recognition.template_builder import TemplateBuilder
from services.storage.object_storage import LocalObjectStorage

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    redis = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
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
    )
    LOGGER.info("api_started", extra={"app_name": settings.app_name, "app_env": settings.app_env})
    yield
    await redis.aclose()
    await engine.dispose()
    LOGGER.info("api_stopped")


app = FastAPI(title="Campus Face Recognition Attendance System", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

