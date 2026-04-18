from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_attendance_read_service, get_recognition_service
from db.schemas.attendance import AttendanceCheckinRequest, AttendanceCheckinResponse, AttendanceLogsResponse, AttendanceStatusResponse
from db.schemas.recognition import RecognitionRequest
from services.attendance.service import AttendanceReadService
from services.recognition.recognition_service import RecognitionService

router = APIRouter()


@router.post("/attendance/checkin", response_model=AttendanceCheckinResponse)
async def attendance_checkin(request: AttendanceCheckinRequest, service: RecognitionService = Depends(get_recognition_service)) -> AttendanceCheckinResponse:
    try:
        return await service.recognize(RecognitionRequest(device_code=request.device_code, frames=request.frames, session_code=request.session_code), event_type="checkin", require_session=True)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/attendance/status/{session_code}", response_model=AttendanceStatusResponse)
async def attendance_status(session_code: str, service: AttendanceReadService = Depends(get_attendance_read_service)) -> AttendanceStatusResponse:
    payload = await service.status(session_code)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attendance session not found")
    return payload


@router.get("/attendance/logs/{session_code}", response_model=AttendanceLogsResponse)
async def attendance_logs(session_code: str, service: AttendanceReadService = Depends(get_attendance_read_service)) -> AttendanceLogsResponse:
    return await service.logs(session_code)

