from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from db.repositories.attendance import AttendanceRepository, AttendanceSessionProjection
from db.schemas.attendance_sessions import AttendanceSessionCreateRequest, AttendanceSessionRead, AttendanceSessionUpdateRequest


class AttendanceSessionConflictError(ValueError):
    pass


class AttendanceSessionService:
    def __init__(self, attendance_repository: AttendanceRepository) -> None:
        self.attendance_repository = attendance_repository

    async def list_sessions(self) -> list[AttendanceSessionRead]:
        return [self._read(projection) for projection in await self.attendance_repository.list_session_projections()]

    async def get_session(self, session_id: UUID) -> AttendanceSessionRead | None:
        projection = await self.attendance_repository.get_session_projection(session_id)
        if projection is None:
            return None
        return self._read(projection)

    async def create_session(self, request: AttendanceSessionCreateRequest) -> AttendanceSessionRead:
        try:
            session = await self.attendance_repository.create_session(
                session_code=request.session_code,
                session_name=request.session_name,
                session_kind=request.session_kind,
                cooldown_seconds=request.cooldown_seconds,
                starts_at=request.starts_at,
                ends_at=request.ends_at,
                is_active=request.is_active,
            )
        except ValueError as exc:
            raise AttendanceSessionConflictError(str(exc)) from exc
        projection = await self.attendance_repository.get_session_projection(session.id)
        if projection is None:
            raise LookupError(f"attendance session {session.id} not found after create")
        return self._read(projection)

    async def update_session(self, session_id: UUID, request: AttendanceSessionUpdateRequest) -> AttendanceSessionRead:
        try:
            session = await self.attendance_repository.update_session(
                session_id=session_id,
                session_code=request.session_code,
                session_name=request.session_name,
                session_kind=request.session_kind,
                cooldown_seconds=request.cooldown_seconds,
                starts_at=request.starts_at,
                ends_at=request.ends_at,
                is_active=request.is_active,
            )
        except ValueError as exc:
            raise AttendanceSessionConflictError(str(exc)) from exc
        projection = await self.attendance_repository.get_session_projection(session.id)
        if projection is None:
            raise LookupError(f"attendance session {session.id} not found after update")
        return self._read(projection)

    async def activate_session(self, session_id: UUID) -> AttendanceSessionRead:
        session = await self.attendance_repository.activate_session(session_id)
        projection = await self.attendance_repository.get_session_projection(session.id)
        if projection is None:
            raise LookupError(f"attendance session {session.id} not found after activate")
        return self._read(projection)

    async def close_session(self, session_id: UUID) -> AttendanceSessionRead:
        session = await self.attendance_repository.close_session(session_id, datetime.now(timezone.utc))
        projection = await self.attendance_repository.get_session_projection(session.id)
        if projection is None:
            raise LookupError(f"attendance session {session.id} not found after close")
        return self._read(projection)

    @staticmethod
    def _read(projection: AttendanceSessionProjection) -> AttendanceSessionRead:
        return AttendanceSessionRead(
            session_id=projection.session.id,
            session_code=projection.session.session_code,
            session_name=projection.session.session_name,
            session_kind=projection.session.session_kind,
            is_active=projection.session.is_active,
            cooldown_seconds=projection.session.cooldown_seconds,
            starts_at=projection.session.starts_at,
            ends_at=projection.session.ends_at,
            total_logs=projection.total_logs,
            recognized=projection.recognized,
            cooldown=projection.cooldown,
            unknown=projection.unknown,
            last_event_at=projection.last_event_at,
            created_at=projection.session.created_at,
            updated_at=projection.session.updated_at,
        )
