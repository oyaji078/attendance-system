from __future__ import annotations

from datetime import datetime, timezone, time, timedelta
from uuid import UUID

from db.domain.attendance import normalize_session_kind
from db.repositories.attendance import AttendanceRepository, AttendanceSessionProjection
from db.schemas.attendance_sessions import AttendanceSessionCreateRequest, AttendanceSessionRead, AttendanceSessionUpdateRequest, ResolvedAttendanceSession

WITA_TZ = timezone(timedelta(hours=8))
WITA_DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class AttendanceSessionConflictError(ValueError):
    pass


class AttendanceSessionService:
    def __init__(self, attendance_repository: AttendanceRepository) -> None:
        self.attendance_repository = attendance_repository

    async def list_sessions(self, *, include_deleted: bool = False) -> list[AttendanceSessionRead]:
        return [self._read(projection) for projection in await self.attendance_repository.list_session_projections(include_deleted=include_deleted)]

    async def list_active_sessions(self) -> list[AttendanceSessionRead]:
        now = datetime.now(timezone.utc)
        return [item for item in await self.list_sessions() if self._is_currently_available(item, now)]

    async def get_session(self, session_id: UUID) -> AttendanceSessionRead | None:
        projection = await self.attendance_repository.get_session_projection(session_id)
        if projection is None:
            return None
        return self._read(projection)

    async def create_session(self, request: AttendanceSessionCreateRequest) -> AttendanceSessionRead:
        try:
            session = await self.attendance_repository.create_session(
                session_code=request.session_code or await self.next_session_code(request.starts_at),
                session_name=request.session_name,
                session_kind=normalize_session_kind(request.session_kind),
                class_id=request.class_id,
                lecturer_id=request.lecturer_id,
                device_code=request.device_code,
                cooldown_seconds=request.cooldown_seconds,
                starts_at=request.starts_at,
                ends_at=request.ends_at,
                is_active=request.is_active,
                repeat_days=request.repeat_days,
                start_time=request.start_time,
                end_time=request.end_time,
                tz=request.timezone,
            )
        except ValueError as exc:
            raise AttendanceSessionConflictError(str(exc)) from exc
        projection = await self.attendance_repository.get_session_projection(session.id)
        if projection is None:
            raise LookupError(f"attendance session {session.id} not found after create")
        return self._read(projection)

    async def update_session(self, session_id: UUID, request: AttendanceSessionUpdateRequest) -> AttendanceSessionRead:
        existing = await self.attendance_repository.get_session_by_id(session_id)
        if existing is None:
            raise LookupError(f"attendance session {session_id} not found")
        try:
            session = await self.attendance_repository.update_session(
                session_id=session_id,
                session_code=request.session_code or existing.session_code,
                session_name=request.session_name,
                session_kind=normalize_session_kind(request.session_kind),
                class_id=request.class_id,
                lecturer_id=request.lecturer_id,
                device_code=request.device_code,
                cooldown_seconds=request.cooldown_seconds,
                starts_at=request.starts_at,
                ends_at=request.ends_at,
                is_active=request.is_active,
                repeat_days=request.repeat_days,
                start_time=request.start_time,
                end_time=request.end_time,
                tz=request.timezone,
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

    async def deactivate_session(self, session_id: UUID) -> AttendanceSessionRead:
        session = await self.attendance_repository.deactivate_session(session_id)
        projection = await self.attendance_repository.get_session_projection(session.id)
        if projection is None:
            raise LookupError(f"attendance session {session.id} not found after deactivate")
        return self._read(projection)

    async def delete_session(self, session_id: UUID) -> dict[str, int | str]:
        session = await self.attendance_repository.get_session_by_id(session_id, include_deleted=True)
        if session is None:
            raise LookupError(f"attendance session {session_id} not found")
        total_logs = await self.attendance_repository.count_logs_for_session(session_id)
        if total_logs > 0:
            await self.attendance_repository.archive_session(session_id, datetime.now(timezone.utc))
            return {"status": "archived", "logs": total_logs}
        deleted = await self.attendance_repository.hard_delete_session(session_id)
        return {"status": "deleted", "logs": total_logs, "deleted": deleted}

    async def next_session_code(self, starts_at: datetime | None = None) -> str:
        timestamp = (starts_at or datetime.now().astimezone()).astimezone()
        prefix = f"ABS-{timestamp:%y%m%d-%H%M}"
        next_number = 1
        while next_number <= 9999:
            candidate = f"{prefix}-{next_number:04d}"
            if not await self.attendance_repository.session_code_exists(candidate):
                return candidate
            next_number += 1
        raise AttendanceSessionConflictError("Tidak dapat membuat kode sesi unik.")

    async def resolve_for_class(self, class_id: UUID | None, now: datetime | None = None) -> tuple[str, ResolvedAttendanceSession | None, list[ResolvedAttendanceSession]]:
        if class_id is None:
            return "no_matching_session", None, []
        projections = await self.attendance_repository.list_available_session_projections_for_class(class_id, now or datetime.now(timezone.utc))
        matches = [self._resolved_read(projection) for projection in projections]
        if len(matches) == 1:
            return "resolved", matches[0], matches
        if not matches:
            return "no_matching_session", None, []
        return "multiple_matching_sessions", None, matches

    @staticmethod
    def _read(projection: AttendanceSessionProjection) -> AttendanceSessionRead:
        return AttendanceSessionRead(
            session_id=projection.session.id,
            session_code=projection.session.session_code,
            session_name=projection.session.session_name,
            session_kind=normalize_session_kind(projection.session.session_kind),
            class_id=projection.session.class_id,
            class_code=projection.class_code,
            class_name=projection.class_name,
            lecturer_id=projection.session.lecturer_id,
            lecturer_name=projection.lecturer_name,
            device_code=projection.session.device_code,
            is_active=projection.session.is_active,
            is_deleted=projection.session.is_deleted,
            cooldown_seconds=projection.session.cooldown_seconds,
            starts_at=projection.session.starts_at,
            ends_at=projection.session.ends_at,
            repeat_days=projection.session.repeat_days,
            start_time=projection.session.start_time,
            end_time=projection.session.end_time,
            timezone=projection.session.timezone or "Asia/Makassar",
            total_logs=projection.total_logs,
            recognized=projection.recognized,
            cooldown=projection.cooldown,
            unknown=projection.unknown,
            last_event_at=projection.last_event_at,
            created_at=projection.session.created_at,
            updated_at=projection.session.updated_at,
            deleted_at=projection.session.deleted_at,
        )

    @staticmethod
    def _resolved_read(projection: AttendanceSessionProjection) -> ResolvedAttendanceSession:
        return ResolvedAttendanceSession(
            session_id=projection.session.id,
            session_code=projection.session.session_code,
            session_name=projection.session.session_name,
            class_id=projection.session.class_id,
            class_name=projection.class_name,
            lecturer_id=projection.session.lecturer_id,
            lecturer_name=projection.lecturer_name,
            start_time=projection.session.starts_at,
            end_time=projection.session.ends_at,
        )

    @staticmethod
    def _is_currently_available(item: AttendanceSessionRead, now: datetime) -> bool:
        if not item.is_active:
            return False
        if item.repeat_days is not None and item.start_time is not None:
            now_wita = AttendanceSessionService._as_utc(now).astimezone(WITA_TZ)
            today_wita = WITA_DAY_NAMES[now_wita.weekday()]
            current_time_wita = now_wita.time()
            if today_wita not in item.repeat_days:
                return False
            if item.start_time is not None and current_time_wita < item.start_time:
                return False
            if item.end_time is not None and current_time_wita > item.end_time:
                return False
            return True
        starts_at = AttendanceSessionService._as_utc(item.starts_at)
        ends_at = AttendanceSessionService._as_utc(item.ends_at)
        if starts_at is not None and starts_at > now:
            return False
        if ends_at is not None and ends_at < now:
            return False
        return True

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
