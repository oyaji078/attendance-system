from __future__ import annotations

from uuid import UUID

from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import FaceSample
from db.models.vector import normalize_embedding_for_db


class FaceSampleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, sample: FaceSample) -> FaceSample:
        sample.embedding = normalize_embedding_for_db(sample.embedding)
        self.session.add(sample)
        await self.session.flush()
        return sample

    async def list_for_enrollment_session(self, enrollment_session_id: UUID) -> list[FaceSample]:
        result = await self.session.execute(
            select(FaceSample).where(FaceSample.enrollment_session_id == enrollment_session_id).order_by(FaceSample.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_person(self, person_id: UUID, *, active_only: bool = True) -> list[FaceSample]:
        statement = select(FaceSample).where(FaceSample.person_id == person_id)
        if active_only:
            statement = statement.where(FaceSample.is_active.is_(True), FaceSample.is_deleted.is_(False))
        result = await self.session.execute(statement.order_by(FaceSample.created_at.asc()))
        return list(result.scalars().all())

    async def latest_for_person(self, person_id: UUID, *, active_only: bool = True) -> FaceSample | None:
        statement = select(FaceSample).where(FaceSample.person_id == person_id)
        if active_only:
            statement = statement.where(FaceSample.is_active.is_(True), FaceSample.is_deleted.is_(False))
        result = await self.session.execute(
            statement.order_by(FaceSample.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def delete_for_person(self, person_id: UUID) -> int:
        result = await self.session.execute(delete(FaceSample).where(FaceSample.person_id == person_id))
        return int(result.rowcount or 0)

    async def deactivate_for_person(self, person_id: UUID) -> int:
        result = await self.session.execute(
            update(FaceSample)
            .where(FaceSample.person_id == person_id, FaceSample.is_active.is_(True))
            .values(is_active=False, is_deleted=True, deleted_at=datetime.now(timezone.utc))
        )
        return int(result.rowcount or 0)
