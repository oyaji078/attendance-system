from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

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


@dataclass(slots=True)
class AttendanceSessionProjection:
    session: AttendanceSession
    total_logs: int
    recognized: int
    cooldown: int
    unknown: int
    last_event_at: datetime | None


class AttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _session_projection_statement():
        return (
            select(
                AttendanceSession,
                func.count(AttendanceLog.id).label("total_logs"),
                func.sum(case((AttendanceLog.decision == "recognized", 1), else_=0)).label("recognized"),
                func.sum(case((AttendanceLog.decision == "cooldown", 1), else_=0)).label("cooldown"),
                func.sum(case((AttendanceLog.decision == "unknown", 1), else_=0)).label("unknown"),
                func.max(AttendanceLog.created_at).label("last_event_at"),
            )
            .outerjoin(AttendanceLog, AttendanceLog.session_id == AttendanceSession.id)
            .group_by(AttendanceSession.id)
        )

    async def get_session(self, session_code: str) -> AttendanceSession | None:
        result = await self.session.execute(select(AttendanceSession).where(AttendanceSession.session_code == session_code))
        return result.scalar_one_or_none()

    async def get_session_by_id(self, session_id: UUID) -> AttendanceSession | None:
        result = await self.session.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
        return result.scalar_one_or_none()

    async def get_session_projection(self, session_id: UUID) -> AttendanceSessionProjection | None:
        result = await self.session.execute(self._session_projection_statement().where(AttendanceSession.id == session_id))
        row = result.one_or_none()
        if row is None:
            return None
        return self._projection_from_row(row)

    async def list_session_projections(self) -> list[AttendanceSessionProjection]:
        result = await self.session.execute(
            self._session_projection_statement().order_by(AttendanceSession.created_at.desc(), AttendanceSession.session_code.asc())
        )
        return [self._projection_from_row(row) for row in result.all()]

    async def create_session(
        self,
        session_code: str,
        session_name: str,
        session_kind: str,
        cooldown_seconds: int,
        starts_at: datetime | None,
        ends_at: datetime | None,
        is_active: bool,
    ) -> AttendanceSession:
        await self._ensure_session_code_available(session_code)
        session = AttendanceSession(
            session_code=session_code,
            session_name=session_name,
            session_kind=session_kind,
            cooldown_seconds=cooldown_seconds,
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=is_active,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def update_session(
        self,
        session_id: UUID,
        session_code: str,
        session_name: str,
        session_kind: str,
        cooldown_seconds: int,
        starts_at: datetime | None,
        ends_at: datetime | None,
        is_active: bool,
    ) -> AttendanceSession:
        session = await self.get_session_by_id(session_id)
        if session is None:
            raise LookupError(f"attendance session {session_id} not found")
        await self._ensure_session_code_available(session_code, exclude_session_id=session_id)
        session.session_code = session_code
        session.session_name = session_name
        session.session_kind = session_kind
        session.cooldown_seconds = cooldown_seconds
        session.starts_at = starts_at
        session.ends_at = ends_at
        session.is_active = is_active
        await self.session.flush()
        return session

    async def activate_session(self, session_id: UUID) -> AttendanceSession:
        session = await self.get_session_by_id(session_id)
        if session is None:
            raise LookupError(f"attendance session {session_id} not found")
        session.is_active = True
        await self.session.flush()
        return session

    async def close_session(self, session_id: UUID, closed_at: datetime) -> AttendanceSession:
        session = await self.get_session_by_id(session_id)
        if session is None:
            raise LookupError(f"attendance session {session_id} not found")
        session.is_active = False
        if session.ends_at is None or session.ends_at > closed_at:
            session.ends_at = closed_at
        await self.session.flush()
        return session

    async def add_log(self, log: AttendanceLog) -> AttendanceLog:
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_status(self, session_code: str) -> AttendanceStatusProjection | None:
        result = await self.session.execute(self._session_projection_statement().where(AttendanceSession.session_code == session_code))
        row = result.one_or_none()
        if row is None:
            return None
        projection = self._projection_from_row(row)
        return AttendanceStatusProjection(
            session=projection.session,
            total_logs=projection.total_logs,
            recognized=projection.recognized,
            cooldown=projection.cooldown,
            unknown=projection.unknown,
            last_event_at=projection.last_event_at,
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

    @staticmethod
    def availability_reason(session: AttendanceSession, now: datetime | None = None) -> str | None:
        timestamp = now or datetime.now(timezone.utc)
        if not session.is_active:
            return "attendance_session_inactive"
        if session.starts_at is not None and timestamp < session.starts_at:
            return "attendance_session_not_started"
        if session.ends_at is not None and timestamp > session.ends_at:
            return "attendance_session_ended"
        return None

    async def _ensure_session_code_available(self, session_code: str, exclude_session_id: UUID | None = None) -> None:
        existing = await self.get_session(session_code)
        if existing is None:
            return
        if exclude_session_id is not None and existing.id == exclude_session_id:
            return
        raise ValueError(f"session_code {session_code} already exists")

    @staticmethod
    def _projection_from_row(row: tuple[AttendanceSession, int, int, int, int, datetime | None]) -> AttendanceSessionProjection:
        session, total_logs, recognized, cooldown, unknown, last_event_at = row
        return AttendanceSessionProjection(
            session=session,
            total_logs=int(total_logs or 0),
            recognized=int(recognized or 0),
            cooldown=int(cooldown or 0),
            unknown=int(unknown or 0),
            last_event_at=last_event_at,
        )
