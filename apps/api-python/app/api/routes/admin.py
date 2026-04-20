from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AppContainer, get_admin_service, get_attendance_session_service, get_container, get_session
from db.repositories.device_configs import DeviceConfigRepository
from db.schemas.admin import AdminActionResponse, AdminMetricsResponse, AdminPersonResponse
from db.schemas.attendance_sessions import AttendanceSessionCreateRequest, AttendanceSessionListResponse, AttendanceSessionRead, AttendanceSessionUpdateRequest
from db.schemas.device import DeviceConfigRead, DeviceConfigWrite
from db.schemas.persons import PersonCreateRequest, PersonListResponse, PersonRead, PersonUpdateRequest
from services.attendance.session_service import AttendanceSessionConflictError, AttendanceSessionService
from services.recognition.admin_service import AdminService, PersonConflictError

router = APIRouter()


@router.put("/admin/devices/config/{device_code}", response_model=DeviceConfigRead)
async def update_device_config(device_code: str, request: DeviceConfigWrite, container: AppContainer = Depends(get_container), session: AsyncSession = Depends(get_session)) -> DeviceConfigRead:
    repository = DeviceConfigRepository(session)
    config = await repository.upsert(
        device_code,
        {
            "device_name": request.device_name,
            "location_hint": request.location_hint,
            "det_thresh": request.det_thresh,
            "det_size_width": request.det_size[0],
            "det_size_height": request.det_size[1],
            "max_faces": request.max_faces,
            "min_face_width_px": request.min_face_width_px,
            "min_brightness": request.min_brightness,
            "min_blur_score": request.min_blur_score,
            "similarity_threshold": request.similarity_threshold,
            "liveness_threshold": request.liveness_threshold,
            "multi_frame_confirm": request.multi_frame_confirm,
            "accepted_per_pose": request.accepted_per_pose,
            "cooldown_seconds": request.cooldown_seconds,
            "is_enabled": request.is_enabled,
        },
    )
    await session.commit()
    await session.refresh(config)
    heartbeat = await container.cache.get_device_heartbeat(device_code)
    return DeviceConfigRead(
        id=config.id,
        device_code=config.device_code,
        device_name=config.device_name,
        location_hint=config.location_hint,
        det_thresh=config.det_thresh,
        det_size=[config.det_size_width, config.det_size_height],
        max_faces=config.max_faces,
        min_face_width_px=config.min_face_width_px,
        min_brightness=config.min_brightness,
        min_blur_score=config.min_blur_score,
        similarity_threshold=config.similarity_threshold,
        liveness_threshold=config.liveness_threshold,
        multi_frame_confirm=config.multi_frame_confirm,
        accepted_per_pose=config.accepted_per_pose,
        cooldown_seconds=config.cooldown_seconds,
        is_enabled=config.is_enabled,
        updated_at=config.updated_at,
        heartbeat=None if heartbeat is None else heartbeat,
    )


@router.post("/admin/reindex", response_model=AdminActionResponse)
async def admin_reindex(service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session)) -> AdminActionResponse:
    await service.reindex()
    await session.commit()
    return AdminActionResponse(status="ok", detail="HNSW index reindexed")


@router.post("/admin/rebuild-all-templates", response_model=AdminActionResponse)
async def rebuild_all_templates(service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session)) -> AdminActionResponse:
    rebuilt = await service.rebuild_all_templates()
    await session.commit()
    return AdminActionResponse(status="ok", detail=f"rebuilt {rebuilt} active templates")


@router.get("/admin/metrics", response_model=AdminMetricsResponse)
async def admin_metrics(service: AdminService = Depends(get_admin_service)) -> AdminMetricsResponse:
    return await service.metrics()


@router.get("/admin/person/{student_id}", response_model=AdminPersonResponse)
async def admin_person(student_id: str, service: AdminService = Depends(get_admin_service)) -> AdminPersonResponse:
    payload = await service.person_detail(student_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person not found")
    return payload


@router.get("/admin/persons", response_model=PersonListResponse)
async def list_persons(service: AdminService = Depends(get_admin_service)) -> PersonListResponse:
    return PersonListResponse(items=await service.list_persons())


@router.post("/admin/persons", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
async def create_person(request: PersonCreateRequest, service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session)) -> PersonRead:
    try:
        payload = await service.create_person(request)
    except PersonConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return payload


@router.get("/admin/persons/{person_id}", response_model=PersonRead)
async def get_person(person_id: UUID, service: AdminService = Depends(get_admin_service)) -> PersonRead:
    payload = await service.get_person(person_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person not found")
    return payload


@router.put("/admin/persons/{person_id}", response_model=PersonRead)
async def update_person(person_id: UUID, request: PersonUpdateRequest, service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session)) -> PersonRead:
    try:
        payload = await service.update_person(person_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PersonConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return payload


@router.patch("/admin/persons/{person_id}/deactivate", response_model=PersonRead)
async def deactivate_person(person_id: UUID, service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session)) -> PersonRead:
    try:
        payload = await service.deactivate_person(person_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return payload


@router.patch("/admin/persons/{person_id}/reactivate", response_model=PersonRead)
async def reactivate_person(person_id: UUID, service: AdminService = Depends(get_admin_service), session: AsyncSession = Depends(get_session)) -> PersonRead:
    try:
        payload = await service.reactivate_person(person_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return payload


@router.get("/admin/attendance-sessions", response_model=AttendanceSessionListResponse)
async def list_attendance_sessions(service: AttendanceSessionService = Depends(get_attendance_session_service)) -> AttendanceSessionListResponse:
    return AttendanceSessionListResponse(items=await service.list_sessions())


@router.post("/admin/attendance-sessions", response_model=AttendanceSessionRead, status_code=status.HTTP_201_CREATED)
async def create_attendance_session(
    request: AttendanceSessionCreateRequest,
    service: AttendanceSessionService = Depends(get_attendance_session_service),
    session: AsyncSession = Depends(get_session),
) -> AttendanceSessionRead:
    try:
        payload = await service.create_session(request)
    except AttendanceSessionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return payload


@router.get("/admin/attendance-sessions/{session_id}", response_model=AttendanceSessionRead)
async def get_attendance_session(session_id: UUID, service: AttendanceSessionService = Depends(get_attendance_session_service)) -> AttendanceSessionRead:
    payload = await service.get_session(session_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attendance session not found")
    return payload


@router.put("/admin/attendance-sessions/{session_id}", response_model=AttendanceSessionRead)
async def update_attendance_session(
    session_id: UUID,
    request: AttendanceSessionUpdateRequest,
    service: AttendanceSessionService = Depends(get_attendance_session_service),
    session: AsyncSession = Depends(get_session),
) -> AttendanceSessionRead:
    try:
        payload = await service.update_session(session_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AttendanceSessionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return payload


@router.patch("/admin/attendance-sessions/{session_id}/activate", response_model=AttendanceSessionRead)
async def activate_attendance_session(
    session_id: UUID,
    service: AttendanceSessionService = Depends(get_attendance_session_service),
    session: AsyncSession = Depends(get_session),
) -> AttendanceSessionRead:
    try:
        payload = await service.activate_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return payload


@router.patch("/admin/attendance-sessions/{session_id}/close", response_model=AttendanceSessionRead)
async def close_attendance_session(
    session_id: UUID,
    service: AttendanceSessionService = Depends(get_attendance_session_service),
    session: AsyncSession = Depends(get_session),
) -> AttendanceSessionRead:
    try:
        payload = await service.close_session(session_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await session.commit()
    return payload
