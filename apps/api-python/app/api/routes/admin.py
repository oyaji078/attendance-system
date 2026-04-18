from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AppContainer, get_admin_service, get_container, get_session
from db.repositories.device_configs import DeviceConfigRepository
from db.schemas.admin import AdminActionResponse, AdminMetricsResponse, AdminPersonResponse
from db.schemas.device import DeviceConfigRead, DeviceConfigWrite
from services.recognition.admin_service import AdminService

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

