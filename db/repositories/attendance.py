from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import AttendanceLog, AttendanceSession, Person


@dataclass(slots=True)
class AttendanceStatusProjection:
    session: AttendanceSession
    total_logs: int
    recognized: int
    cooldown: int
    unknown: int
    last_event_at: datetime | None


class AttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_session(self, session_code: str) -> AttendanceSession | None:
        result = await self.session.execute(select(AttendanceSession).where(AttendanceSession.session_code == session_code))
        return result.scalar_one_or_none()

    async def add_log(self, log: AttendanceLog) -> AttendanceLog:
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_status(self, session_code: str) -> AttendanceStatusProjection | None:
        result = await self.session.execute(
            select(
                AttendanceSession,
                func.count(AttendanceLog.id).label("total_logs"),
                func.sum(case((AttendanceLog.decision == "recognized", 1), else_=0)).label("recognized"),
                func.sum(case((AttendanceLog.decision == "cooldown", 1), else_=0)).label("cooldown"),
                func.sum(case((AttendanceLog.decision == "unknown", 1), else_=0)).label("unknown"),
                func.max(AttendanceLog.created_at).label("last_event_at"),
            )
            .outerjoin(AttendanceLog, AttendanceLog.session_id == AttendanceSession.id)
            .where(AttendanceSession.session_code == session_code)
            .group_by(AttendanceSession.id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        session, total_logs, recognized, cooldown, unknown, last_event_at = row
        return AttendanceStatusProjection(
            session=session,
            total_logs=int(total_logs or 0),
            recognized=int(recognized or 0),
            cooldown=int(cooldown or 0),
            unknown=int(unknown or 0),
            last_event_at=last_event_at,
        )

    async def list_logs(self, session_code: str) -> list[tuple[AttendanceLog, Person | None]]:
        result = await self.session.execute(
            select(AttendanceLog, Person)
            .join(AttendanceSession, AttendanceSession.id == AttendanceLog.session_id)
            .outerjoin(Person, Person.id == AttendanceLog.person_id)
            .where(AttendanceSession.session_code == session_code)
            .order_by(AttendanceLog.created_at.desc())
        )
        return list(result.all())

    async def metrics(self) -> dict[str, int]:
        window_start = datetime.now(timezone.utc) - timedelta(hours=24)
        total_logs = await self.session.execute(select(func.count(AttendanceLog.id)))
        recognized = await self.session.execute(
            select(func.count(AttendanceLog.id)).where(
                AttendanceLog.decision == "recognized",
                AttendanceLog.created_at >= window_start,
            )
        )
        return {
            "total_logs": int(total_logs.scalar_one()),
            "recognized_last_24h": int(recognized.scalar_one()),
        }

