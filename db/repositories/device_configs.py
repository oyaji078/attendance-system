from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import DeviceConfig


class DeviceConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_code(self, device_code: str) -> DeviceConfig | None:
        result = await self.session.execute(select(DeviceConfig).where(DeviceConfig.device_code == device_code))
        return result.scalar_one_or_none()

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
