from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from uuid import UUID

from app.core.config import Settings
from app.core.csrf import CsrfProtection
from app.core.security import verify_session_token
from db.models.entities import AdminUser
from db.repositories.admin_users import AdminUserRepository
from db.repositories.attendance import AttendanceRepository
from db.repositories.device_configs import DeviceConfigRepository
from db.repositories.face_samples import FaceSampleRepository
from db.repositories.face_templates import FaceTemplateRepository
from db.repositories.metrics import MetricsRepository
from db.repositories.persons import PersonRepository
from services.attendance.cache import RedisStateCache
from services.auth_service import AuthService
from services.attendance.service import AttendanceReadService
from services.attendance.session_service import AttendanceSessionService
from services.liveness.color_challenge import ColorChallengeService
from services.liveness.service import HeuristicPassiveLivenessService
from services.quality.service import QualityGate
from services.recognition.admin_service import AdminService
from services.recognition.enrollment_service import EnrollmentService
from services.recognition.decision_engine import MultiFrameDecisionEngine
from services.recognition.frame_processor import RecognitionFrameProcessor, TemplateMatcher
from services.recognition.logger import RecognitionAuditLogger
from services.recognition.pipeline import InsightFaceEmbeddingPipeline
from services.recognition.pose_validator import PoseValidator
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
    csrf_protection: CsrfProtection | None = None
    challenge_service: ColorChallengeService | None = None


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


async def get_session(container: AppContainer = Depends(get_container)) -> AsyncIterator[AsyncSession]:
    async with container.session_factory() as session:
        yield session


def get_auth_service(session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> AuthService:
    return AuthService(AdminUserRepository(session), container.settings)


async def get_current_admin_user(
    request: Request,
    service: AuthService = Depends(get_auth_service),
    container: AppContainer = Depends(get_container),
) -> AdminUser:
    token = request.cookies.get("admin_session")
    auth_header = request.headers.get("authorization")
    if not token and auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    payload = verify_session_token(token or "", container.settings.auth_secret_key)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login admin diperlukan.")
    try:
        admin_id = UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesi login tidak valid.") from exc
    user = await service.get_active_user(admin_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesi login tidak valid.")
    return user


def require_admin(user: AdminUser = Depends(get_current_admin_user)) -> AdminUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses admin diperlukan.")
    return user


def require_admin_or_operator(user: AdminUser = Depends(get_current_admin_user)) -> AdminUser:
    if user.role not in {"admin", "operator"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses admin/operator diperlukan.")
    return user


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
        pose_validator=PoseValidator(),
        challenge_service=container.challenge_service,
    )


def get_recognition_service(session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> RecognitionService:
    attendance_repository = AttendanceRepository(session)
    template_repository = FaceTemplateRepository(session)
    return RecognitionService(
        session=session,
        device_repository=DeviceConfigRepository(session),
        attendance_repository=attendance_repository,
        frame_processor=RecognitionFrameProcessor(
            pipeline=container.pipeline,
            liveness_service=container.liveness_service,
            quality_gate=container.quality_gate,
            template_matcher=TemplateMatcher(
                template_repository,
                confidence_threshold=container.settings.recognition_confidence_threshold,
            ),
            quality_mode=container.settings.attendance_quality_mode,
        ),
        decision_engine=MultiFrameDecisionEngine(
            container.cache,
            confidence_threshold=container.settings.recognition_confidence_threshold,
            candidate_margin_threshold=container.settings.recognition_candidate_margin_threshold,
        ),
        audit_logger=RecognitionAuditLogger(attendance_repository),
        cache=container.cache,
        object_storage=container.object_storage,
        slow_request_ms=container.settings.recognition_slow_request_ms,
        challenge_service=container.challenge_service,
    )


def get_attendance_read_service(session: AsyncSession = Depends(get_session)) -> AttendanceReadService:
    return AttendanceReadService(AttendanceRepository(session))


def get_attendance_session_service(session: AsyncSession = Depends(get_session)) -> AttendanceSessionService:
    return AttendanceSessionService(AttendanceRepository(session))


def get_admin_service(session: AsyncSession = Depends(get_session), container: AppContainer = Depends(get_container)) -> AdminService:
    return AdminService(
        person_repository=PersonRepository(session),
        sample_repository=FaceSampleRepository(session),
        template_repository=FaceTemplateRepository(session),
        attendance_repository=AttendanceRepository(session),
        metrics_repository=MetricsRepository(session),
        template_builder=container.template_builder,
        object_storage=container.object_storage,
    )
