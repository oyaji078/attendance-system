import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_enrollment_service, require_admin
from app.core.rate_limiter import rate_limit_enrollment_dependency
from db.schemas.enrollment import EnrollmentFinishRequest, EnrollmentFinishResponse, EnrollmentFrameRequest, EnrollmentFrameResponse, EnrollmentStartRequest, EnrollmentStartResponse
from services.recognition.enrollment_service import EnrollmentService

router = APIRouter(dependencies=[Depends(require_admin), Depends(rate_limit_enrollment_dependency)])
LOGGER = logging.getLogger(__name__)


@router.post("/enroll/start", response_model=EnrollmentStartResponse)
async def enroll_start(request: EnrollmentStartRequest, service: EnrollmentService = Depends(get_enrollment_service)) -> EnrollmentStartResponse:
    try:
        return await service.start(request)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception(
            "enrollment_start_unexpected_error",
            extra={"device_code": request.device_code, "student_id": request.student_id, "error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "enrollment_start_failed",
                "message": "Pendaftaran gagal dimulai. Coba ulangi.",
            },
        ) from exc


@router.post("/enroll/frame", response_model=EnrollmentFrameResponse)
async def enroll_frame(request: EnrollmentFrameRequest, service: EnrollmentService = Depends(get_enrollment_service)) -> EnrollmentFrameResponse:
    try:
        return await service.process_frame(request)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception(
            "enrollment_frame_unexpected_error",
            extra={
                "enrollment_session_id": str(request.enrollment_session_id),
                "device_code": request.device_code,
                "pose": request.pose,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "enrollment_frame_failed",
                "message": "Terjadi kesalahan saat menyimpan wajah. Coba ulangi.",
            },
        ) from exc


@router.post("/enroll/finish", response_model=EnrollmentFinishResponse)
async def enroll_finish(request: EnrollmentFinishRequest, service: EnrollmentService = Depends(get_enrollment_service)) -> EnrollmentFinishResponse:
    try:
        return await service.finish(request)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception(
            "enrollment_finish_unexpected_error",
            extra={"enrollment_session_id": str(request.enrollment_session_id), "error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "enrollment_finish_failed",
                "message": "Terjadi kesalahan saat menyimpan wajah. Coba ulangi.",
            },
        ) from exc


@router.post("/enroll/rebuild-template/{person_id}", response_model=EnrollmentFinishResponse)
async def rebuild_template(person_id: UUID, service: EnrollmentService = Depends(get_enrollment_service)) -> EnrollmentFinishResponse:
    try:
        return await service.rebuild_template(person_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
