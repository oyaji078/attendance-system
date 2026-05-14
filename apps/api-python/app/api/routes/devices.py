from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AppContainer, get_container, get_session
from db.repositories.device_configs import DeviceConfigRepository
from db.schemas.device import DeviceConfigRead, DeviceHeartbeatRead, DeviceHeartbeatWrite

router = APIRouter()


@router.get("/devices/config/{device_code}", response_model=DeviceConfigRead)
async def get_device_config(device_code: str, container: AppContainer = Depends(get_container), session: AsyncSession = Depends(get_session)) -> DeviceConfigRead:
    repository = DeviceConfigRepository(session)
    config = await repository.get_by_code(device_code)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device config not found")
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
        candidate_margin_threshold=config.candidate_margin_threshold,
        liveness_threshold=config.liveness_threshold,
        multi_frame_confirm=config.multi_frame_confirm,
        accepted_per_pose=config.accepted_per_pose,
        cooldown_seconds=config.cooldown_seconds,
        is_enabled=config.is_enabled,
        updated_at=config.updated_at,
        heartbeat=DeviceHeartbeatRead.model_validate(heartbeat) if heartbeat else None,
    )


@router.post("/devices/heartbeat/{device_code}", response_model=DeviceHeartbeatRead)
async def post_device_heartbeat(device_code: str, request: DeviceHeartbeatWrite, container: AppContainer = Depends(get_container), session: AsyncSession = Depends(get_session)) -> DeviceHeartbeatRead:
    repository = DeviceConfigRepository(session)
    config = await repository.get_by_code(device_code)
    if config is None or not config.is_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device config not found")
    await container.cache.set_device_heartbeat(device_code, request.queue_depth, request.agent_version, request.captured_at)
    heartbeat = await container.cache.get_device_heartbeat(device_code)
    if heartbeat is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="heartbeat not persisted")
    return DeviceHeartbeatRead.model_validate(heartbeat)
