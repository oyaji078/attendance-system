from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from db.repositories.attendance import AttendanceRepository
from db.repositories.device_configs import DeviceConfigRepository
from db.repositories.face_samples import FaceSampleRepository
from db.repositories.face_templates import FaceTemplateRepository
from db.repositories.metrics import MetricsRepository
from db.repositories.persons import PersonRepository
from services.attendance.cache import RedisStateCache
from services.attendance.service import AttendanceReadService
from services.liveness.service import HeuristicPassiveLivenessService
from services.quality.service import QualityGate
from services.recognition.admin_service import AdminService
from services.recognition.enrollment_service import EnrollmentService
from services.recognition.pipeline import InsightFaceEmbeddingPipeline
from services.recognition.recognition_service import RecognitionService
from services.recognition.template_builder import TemplateBuilder
from services.storage.object_storage import LocalObjectStorage


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    object_storage: LocalObjectStorage
    cache: RedisStateCache
    pipeline: InsightFaceEmbeddingPipeline
    liveness_service: HeuristicPassiveLivenessService
    quality_gate: QualityGate
    template_builder: TemplateBuilder


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


async def get_session(container: AppContainer = Depends(get_container)) -> AsyncIterator[AsyncSession]:
    async with container.session_factory() as session:
        yield session


def get_enrollment_service(session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> EnrollmentService:
    return EnrollmentService(
        session=session,
        device_repository=DeviceConfigRepository(session),
        person_repository=PersonRepository(session),
        face_sample_repository=FaceSampleRepository(session),
        face_template_repository=FaceTemplateRepository(session),
        cache=container.cache,
        pipeline=container.pipeline,
        liveness_service=container.liveness_service,
        quality_gate=container.quality_gate,
        template_builder=container.template_builder,
        object_storage=container.object_storage,
    )


def get_recognition_service(session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> RecognitionService:
    return RecognitionService(
        session=session,
        device_repository=DeviceConfigRepository(session),
        template_repository=FaceTemplateRepository(session),
        attendance_repository=AttendanceRepository(session),
        cache=container.cache,
        pipeline=container.pipeline,
        liveness_service=container.liveness_service,
        quality_gate=container.quality_gate,
    )


def get_attendance_read_service(session: AsyncSession = Depends(get_session)) -> AttendanceReadService:
    return AttendanceReadService(AttendanceRepository(session))


def get_admin_service(session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> AdminService:
    return AdminService(
        person_repository=PersonRepository(session),
        sample_repository=FaceSampleRepository(session),
        template_repository=FaceTemplateRepository(session),
        attendance_repository=AttendanceRepository(session),
        metrics_repository=MetricsRepository(session),
        template_builder=container.template_builder,
    )

