import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_attendance_read_service, get_attendance_session_service, get_recognition_service
from db.schemas.attendance import (
    AttendanceCheckinRequest,
    AttendanceCheckinResponse,
    AttendanceConfirmRequest,
    AttendanceConfirmResponse,
    AttendanceLogsResponse,
    AttendancePreviewRequest,
    AttendancePreviewResponse,
    AttendanceStatusResponse,
)
from db.schemas.attendance_sessions import AttendanceSessionPublicRead
from db.schemas.recognition import RecognitionRequest
from services.attendance.service import AttendanceReadService
from services.attendance.session_service import AttendanceSessionService
from services.recognition.recognition_service import RecognitionService

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.post("/attendance/checkin", response_model=AttendanceCheckinResponse)
async def attendance_checkin(request: AttendanceCheckinRequest, service: RecognitionService = Depends(get_recognition_service)) -> AttendanceCheckinResponse:
    try:
        return await service.recognize(RecognitionRequest(device_code=request.device_code, frames=request.frames, session_code=request.session_code), event_type="checkin", require_session=True)
    except LookupError as exc:
        LOGGER.warning("attendance_checkin_lookup_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesi absensi belum dipilih.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("attendance_checkin_failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Absensi gagal. Coba ulangi.") from exc


@router.post("/attendance/preview", response_model=AttendancePreviewResponse)
async def attendance_preview(request: AttendancePreviewRequest, service: RecognitionService = Depends(get_recognition_service)) -> AttendancePreviewResponse:
    try:
        return await service.preview_attendance(request)
    except LookupError as exc:
        LOGGER.warning("attendance_preview_lookup_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data perangkat tidak ditemukan.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("attendance_preview_failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengenali wajah. Coba ulangi.") from exc


@router.post("/attendance/confirm", response_model=AttendanceConfirmResponse)
async def attendance_confirm(request: AttendanceConfirmRequest, service: RecognitionService = Depends(get_recognition_service)) -> AttendanceConfirmResponse:
    try:
        return await service.confirm_attendance(request)
    except LookupError as exc:
        LOGGER.warning("attendance_confirm_lookup_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("attendance_confirm_failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Absensi gagal. Coba ulangi.") from exc


@router.get("/attendance/status/{session_code}", response_model=AttendanceStatusResponse)
async def attendance_status(session_code: str, service: AttendanceReadService = Depends(get_attendance_read_service)) -> AttendanceStatusResponse:
    payload = await service.status(session_code)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attendance session not found")
    return payload


@router.get("/attendance/sessions/active", response_model=list[AttendanceSessionPublicRead])
async def active_attendance_sessions(service: AttendanceSessionService = Depends(get_attendance_session_service)) -> list[AttendanceSessionPublicRead]:
    return await service.list_active_sessions()


@router.get("/attendance/logs/{session_code}", response_model=AttendanceLogsResponse)
async def attendance_logs(session_code: str, service: AttendanceReadService = Depends(get_attendance_read_service)) -> AttendanceLogsResponse:
    return await service.logs(session_code)
