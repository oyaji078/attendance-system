from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import FaceSample, Person


class MetricsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def person_counts(self) -> tuple[int, int]:
        total = await self.session.execute(select(func.count(Person.id)))
        active = await self.session.execute(select(func.count(Person.id)).where(Person.is_active.is_(True)))
        return int(total.scalar_one()), int(active.scalar_one())

    async def sample_count(self) -> int:
        result = await self.session.execute(select(func.count(FaceSample.id)))
        return int(result.scalar_one())

