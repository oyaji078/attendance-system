from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import DeviceConfig

logger = logging.getLogger(__name__)

_DEVICE_CONFIG_CACHE_TTL = 60


def _reconstruct_device_config(data: dict) -> DeviceConfig:
    config = DeviceConfig()
    config.id = UUID(data["id"]) if isinstance(data["id"], str) else data["id"]
    config.device_code = data["device_code"]
    config.device_name = data["device_name"]
    config.location_hint = data.get("location_hint")
    config.det_thresh = float(data["det_thresh"])
    config.det_size_width = int(data["det_size_width"])
    config.det_size_height = int(data["det_size_height"])
    config.max_faces = int(data["max_faces"])
    config.min_face_width_px = int(data["min_face_width_px"])
    config.min_brightness = float(data["min_brightness"])
    config.min_blur_score = float(data["min_blur_score"])
    config.similarity_threshold = float(data["similarity_threshold"])
    config.candidate_margin_threshold = float(data["candidate_margin_threshold"])
    config.liveness_threshold = float(data["liveness_threshold"])
    config.multi_frame_confirm = int(data["multi_frame_confirm"])
    config.accepted_per_pose = int(data["accepted_per_pose"])
    config.cooldown_seconds = int(data["cooldown_seconds"])
    config.is_enabled = bool(data["is_enabled"])
    raw_updated = data.get("updated_at")
    if raw_updated is not None:
        config.updated_at = datetime.fromisoformat(raw_updated) if isinstance(raw_updated, str) else raw_updated
    else:
        config.updated_at = datetime.now(timezone.utc)
    return config


def _serialize_device_config(config: DeviceConfig) -> dict:
    return {
        "id": str(config.id),
        "device_code": config.device_code,
        "device_name": config.device_name,
        "location_hint": config.location_hint,
        "det_thresh": config.det_thresh,
        "det_size_width": config.det_size_width,
        "det_size_height": config.det_size_height,
        "max_faces": config.max_faces,
        "min_face_width_px": config.min_face_width_px,
        "min_brightness": config.min_brightness,
        "min_blur_score": config.min_blur_score,
        "similarity_threshold": config.similarity_threshold,
        "candidate_margin_threshold": config.candidate_margin_threshold,
        "liveness_threshold": config.liveness_threshold,
        "multi_frame_confirm": config.multi_frame_confirm,
        "accepted_per_pose": config.accepted_per_pose,
        "cooldown_seconds": config.cooldown_seconds,
        "is_enabled": config.is_enabled,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


class DeviceConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_code(self, device_code: str) -> DeviceConfig | None:
        result = await self.session.execute(select(DeviceConfig).where(DeviceConfig.device_code == device_code))
        return result.scalar_one_or_none()

    async def get_by_code_cached(self, device_code: str, cache: object | None = None) -> DeviceConfig | None:
        if cache is not None:
            cached = await cache.get_device_config_cached(device_code)
            if cached is not None:
                return _reconstruct_device_config(cached)

        config = await self.get_by_code(device_code)
        if config is not None and cache is not None:
            await cache.set_device_config_cached(device_code, _serialize_device_config(config), _DEVICE_CONFIG_CACHE_TTL)
        return config

    async def list_all(self, limit: int | None = None, offset: int = 0) -> list[DeviceConfig]:
        stmt = select(DeviceConfig).order_by(DeviceConfig.device_code.asc())
        if limit is not None:
            stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(self, device_code: str, payload: Mapping[str, object]) -> DeviceConfig:
        config = await self.get_by_code(device_code)
        if config is None:
            config = DeviceConfig(device_code=device_code, **dict(payload))
            self.session.add(config)
        else:
            for key, value in payload.items():
                setattr(config, key, value)
        await self.session.flush()
        return config
