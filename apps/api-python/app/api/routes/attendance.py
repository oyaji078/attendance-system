import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import (
    get_attendance_read_service,
    get_attendance_session_service,
    get_current_admin_user,
    get_recognition_service,
)
from app.core.rate_limiter import rate_limit_attendance_dependency
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
async def attendance_checkin(
    request: AttendanceCheckinRequest,
    service: RecognitionService = Depends(get_recognition_service),
    _: None = Depends(rate_limit_attendance_dependency),
) -> AttendanceCheckinResponse:
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
async def attendance_preview(
    request: AttendancePreviewRequest,
    service: RecognitionService = Depends(get_recognition_service),
    _: None = Depends(rate_limit_attendance_dependency),
) -> AttendancePreviewResponse:
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
async def attendance_confirm(
    request: AttendanceConfirmRequest,
    service: RecognitionService = Depends(get_recognition_service),
    _: None = Depends(rate_limit_attendance_dependency),
) -> AttendanceConfirmResponse:
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
async def attendance_logs(
    session_code: str,
    service: AttendanceReadService = Depends(get_attendance_read_service),
    _: object = Depends(get_current_admin_user),
) -> AttendanceLogsResponse:
    """Roster of a session. Requires a signed-in account: it carries names and
    student IDs, and the kiosk origin is publicly reachable."""
    return await service.logs(session_code)


@router.get("/attendance/classes/active", response_model=list[dict])
async def active_classes(service: AttendanceSessionService = Depends(get_attendance_session_service)) -> list[dict]:
    # list_active_sessions always yields AttendanceSessionRead models.
    class_map: dict[str, dict] = {}
    for session in await service.list_active_sessions():
        if session.class_id is None:
            continue
        cid = str(session.class_id)
        if cid not in class_map:
            class_map[cid] = {
                "class_id": cid,
                "class_code": session.class_code or "",
                "class_name": session.class_name or "",
                "lecturer_name": session.lecturer_name,
                "active_session_count": 0,
            }
        class_map[cid]["active_session_count"] += 1
    return sorted(class_map.values(), key=lambda c: c["class_code"])


@router.get("/attendance/classes/{class_id}/sessions/active", response_model=list[AttendanceSessionPublicRead])
async def active_sessions_for_class(class_id: str, service: AttendanceSessionService = Depends(get_attendance_session_service)) -> list[AttendanceSessionPublicRead]:
    try:
        UUID(class_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid class_id")
    return [s for s in await service.list_active_sessions() if s.class_id is not None and str(s.class_id) == class_id]


@router.get("/attendance/sessions/{session_id}/today-logs", response_model=list[dict])
async def session_today_logs(
    session_id: str,
    timezone: str = "Asia/Makassar",
    service: AttendanceReadService = Depends(get_attendance_read_service),
    _: object = Depends(get_current_admin_user),
):
    """Today's roster for a session. Authenticated for the same reason as
    ``/attendance/logs/{session_code}`` — it returns identifiable students."""
    try:
        sid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session_id")

    # WITA is the only supported timezone for today's logs window.
    # The accepted "timezone" query parameter is accepted for API compatibility
    # and documented purposes; the implementation is fixed to Asia/Makassar.
    wita_tz = dt_timezone(timedelta(hours=8))
    now_wita = datetime.now(wita_tz)
    today_start_wita = now_wita.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end_wita = today_start_wita + timedelta(days=1)
    today_start = today_start_wita.astimezone(dt_timezone.utc)
    today_end = today_end_wita.astimezone(dt_timezone.utc)

    return await service.logs_for_session_today(sid, today_start, today_end)
