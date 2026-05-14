from __future__ import annotations

from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.domain.attendance import ATTENDANCE_SUCCESS_DECISIONS
from db.models.entities import AttendanceLog, ClassGroup, FaceSample, Lecturer, Person


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

    async def lecturer_count(self) -> int:
        result = await self.session.execute(select(func.count(Lecturer.id)).where(Lecturer.is_active.is_(True)))
        return int(result.scalar_one())

    async def class_count(self) -> int:
        result = await self.session.execute(select(func.count(ClassGroup.id)).where(ClassGroup.is_active.is_(True)))
        return int(result.scalar_one())

    async def today_attendance_count(self) -> int:
        start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
        result = await self.session.execute(
            select(func.count(AttendanceLog.id)).where(
                AttendanceLog.created_at >= start,
                AttendanceLog.decision.in_(ATTENDANCE_SUCCESS_DECISIONS),
                AttendanceLog.is_deleted.is_(False),
            )
        )
        return int(result.scalar_one())

    async def today_failed_count(self) -> int:
        start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
        result = await self.session.execute(
            select(func.count(AttendanceLog.id)).where(
                AttendanceLog.created_at >= start,
                ~AttendanceLog.decision.in_(ATTENDANCE_SUCCESS_DECISIONS),
                AttendanceLog.is_deleted.is_(False),
            )
        )
        return int(result.scalar_one())
