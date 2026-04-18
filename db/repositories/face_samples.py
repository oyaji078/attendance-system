from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import FaceSample


class FaceSampleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, sample: FaceSample) -> FaceSample:
        self.session.add(sample)
        await self.session.flush()
        return sample

    async def list_for_enrollment_session(self, enrollment_session_id: UUID) -> list[FaceSample]:
        result = await self.session.execute(
            select(FaceSample).where(FaceSample.enrollment_session_id == enrollment_session_id).order_by(FaceSample.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_person(self, person_id: UUID) -> list[FaceSample]:
        result = await self.session.execute(
            select(FaceSample).where(FaceSample.person_id == person_id).order_by(FaceSample.created_at.asc())
        )
        return list(result.scalars().all())

