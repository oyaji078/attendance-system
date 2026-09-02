from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, time
from uuid import UUID

from sqlalchemy import Text, and_, case, cast, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload

from db.domain.attendance import (
    ATTENDANCE_SUCCESS_DECISIONS,
    COOLDOWN_REASONS,
    normalize_attendance_decision,
    normalize_attendance_event_type,
    normalize_attendance_reason,
    normalize_session_kind,
)
from db.models.entities import AttendanceLog, AttendanceSession, ClassGroup, Lecturer, Person

WITA_TZ = timezone(timedelta(hours=8))
WITA_DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


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
    class_code: str | None = None
    class_name: str | None = None
    lecturer_name: str | None = None


class AttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _session_projection_statement(include_deleted: bool = False):
        session_lecturer = aliased(Lecturer)
        class_lecturer = aliased(Lecturer)
        lecturer_name = func.coalesce(session_lecturer.full_name, class_lecturer.full_name).label("lecturer_name")
        success_condition = AttendanceLog.decision.in_(ATTENDANCE_SUCCESS_DECISIONS)
        cooldown_condition = or_(AttendanceLog.decision == "cooldown", AttendanceLog.reason.in_(COOLDOWN_REASONS))
        unknown_condition = and_(AttendanceLog.id.is_not(None), ~success_condition, ~cooldown_condition)
        statement = (
            select(
                AttendanceSession,
                func.count(AttendanceLog.id).label("total_logs"),
                func.sum(case((success_condition, 1), else_=0)).label("recognized"),
                func.sum(case((cooldown_condition, 1), else_=0)).label("cooldown"),
                func.sum(case((unknown_condition, 1), else_=0)).label("unknown"),
                func.max(AttendanceLog.created_at).label("last_event_at"),
                ClassGroup.class_code,
                ClassGroup.class_name,
                lecturer_name,
            )
            .outerjoin(ClassGroup, ClassGroup.id == AttendanceSession.class_id)
            .outerjoin(session_lecturer, session_lecturer.id == AttendanceSession.lecturer_id)
            .outerjoin(class_lecturer, class_lecturer.id == ClassGroup.lecturer_id)
            .outerjoin(AttendanceLog, AttendanceLog.session_id == AttendanceSession.id)
            .group_by(AttendanceSession.id, ClassGroup.class_code, ClassGroup.class_name, session_lecturer.full_name, class_lecturer.full_name)
        )
        if not include_deleted:
            statement = statement.where(AttendanceSession.is_deleted.is_(False))
        return statement

    @staticmethod
    def _session_available_filter(now: datetime):
        now_wita = AttendanceRepository._as_utc(now).astimezone(WITA_TZ)
        today_wita = WITA_DAY_NAMES[now_wita.weekday()]
        current_time_wita = now_wita.time()
        return (
            AttendanceSession.is_deleted.is_(False),
            AttendanceSession.is_active.is_(True),
            or_(
                AttendanceSession.repeat_days.is_(None),
                # Sessions saved without a schedule hold JSON null, not SQL
                # NULL, so IS NULL alone hid every always-available session.
                cast(AttendanceSession.repeat_days, Text) == "null",
                # repeat_days is a plain JSON column, so .contains() compiles to
                # `json LIKE text`, an operator Postgres does not have. Compare
                # the rendered text instead; the quotes keep day names exact.
                cast(AttendanceSession.repeat_days, Text).like(f'%"{today_wita}"%'),
            ),
            or_(
                AttendanceSession.start_time.is_(None),
                AttendanceSession.start_time <= current_time_wita,
            ),
            or_(
                AttendanceSession.end_time.is_(None),
                AttendanceSession.end_time >= current_time_wita,
            ),
            or_(
                and_(
                    AttendanceSession.repeat_days.is_not(None),
                    AttendanceSession.start_time.is_not(None),
                ),
                and_(
                    AttendanceSession.starts_at.is_(None),
                    AttendanceSession.ends_at.is_(None),
                ),
                and_(
                    AttendanceSession.starts_at.is_(None),
                    AttendanceSession.ends_at.is_not(None),
                    AttendanceSession.ends_at >= now,
                ),
                and_(
                    AttendanceSession.starts_at.is_not(None),
                    AttendanceSession.ends_at.is_(None),
                    AttendanceSession.starts_at <= now,
                ),
                and_(
                    AttendanceSession.starts_at.is_not(None),
                    AttendanceSession.ends_at.is_not(None),
                    AttendanceSession.starts_at <= now,
                    AttendanceSession.ends_at >= now,
                ),
            ),
        )

    async def get_session(self, session_code: str, *, include_deleted: bool = False) -> AttendanceSession | None:
        statement = select(AttendanceSession).where(AttendanceSession.session_code == session_code)
        if not include_deleted:
            statement = statement.where(AttendanceSession.is_deleted.is_(False))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_session_by_id(self, session_id: UUID, *, include_deleted: bool = False) -> AttendanceSession | None:
        statement = select(AttendanceSession).where(AttendanceSession.id == session_id)
        if not include_deleted:
            statement = statement.where(AttendanceSession.is_deleted.is_(False))
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_session_projection(self, session_id: UUID, *, include_deleted: bool = False) -> AttendanceSessionProjection | None:
        result = await self.session.execute(self._session_projection_statement(include_deleted=include_deleted).where(AttendanceSession.id == session_id))
        row = result.one_or_none()
        if row is None:
            return None
        return self._projection_from_row(row)

    async def list_session_projections(self, *, include_deleted: bool = False) -> list[AttendanceSessionProjection]:
        result = await self.session.execute(
            self._session_projection_statement(include_deleted=include_deleted).order_by(AttendanceSession.created_at.desc(), AttendanceSession.session_code.asc())
        )
        return [self._projection_from_row(row) for row in result.all()]

    async def list_available_session_projections_for_class(self, class_id: UUID, now: datetime) -> list[AttendanceSessionProjection]:
        result = await self.session.execute(
            self._session_projection_statement()
            .where(
                AttendanceSession.class_id == class_id,
                *self._session_available_filter(self._as_utc(now)),
            )
            .order_by(AttendanceSession.starts_at.asc().nulls_last(), AttendanceSession.created_at.asc())
        )
        return [self._projection_from_row(row) for row in result.all()]

    async def create_session(
        self,
        session_code: str,
        session_name: str,
        session_kind: str,
        class_id: UUID | None,
        lecturer_id: UUID | None,
        device_code: str | None,
        cooldown_seconds: int,
        starts_at: datetime | None,
        ends_at: datetime | None,
        is_active: bool,
        repeat_days: list[str] | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
        tz: str | None = "Asia/Makassar",
    ) -> AttendanceSession:
        await self._ensure_session_code_available(session_code)
        session = AttendanceSession(
            session_code=session_code,
            session_name=session_name,
            session_kind=normalize_session_kind(session_kind),
            class_id=class_id,
            lecturer_id=lecturer_id,
            device_code=device_code,
            cooldown_seconds=cooldown_seconds,
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=is_active,
            repeat_days=repeat_days,
            start_time=start_time,
            end_time=end_time,
            timezone=tz,
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
        class_id: UUID | None,
        lecturer_id: UUID | None,
        device_code: str | None,
        cooldown_seconds: int,
        starts_at: datetime | None,
        ends_at: datetime | None,
        is_active: bool,
        repeat_days: list[str] | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
        tz: str | None = "Asia/Makassar",
    ) -> AttendanceSession:
        session = await self.get_session_by_id(session_id)
        if session is None:
            raise LookupError(f"attendance session {session_id} not found")
        await self._ensure_session_code_available(session_code, exclude_session_id=session_id)
        session.session_code = session_code
        session.session_name = session_name
        session.session_kind = normalize_session_kind(session_kind)
        session.class_id = class_id
        session.lecturer_id = lecturer_id
        session.device_code = device_code
        session.cooldown_seconds = cooldown_seconds
        session.starts_at = starts_at
        session.ends_at = ends_at
        session.is_active = is_active
        session.repeat_days = repeat_days
        session.start_time = start_time
        session.end_time = end_time
        session.timezone = tz
        await self.session.flush()
        return session

    async def activate_session(self, session_id: UUID) -> AttendanceSession:
        session = await self.get_session_by_id(session_id)
        if session is None:
            raise LookupError(f"attendance session {session_id} not found")
        session.is_active = True
        await self.session.flush()
        return session

    async def deactivate_session(self, session_id: UUID) -> AttendanceSession:
        session = await self.get_session_by_id(session_id)
        if session is None:
            raise LookupError(f"attendance session {session_id} not found")
        session.is_active = False
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

    async def count_logs_for_session(self, session_id: UUID) -> int:
        result = await self.session.execute(select(func.count(AttendanceLog.id)).where(AttendanceLog.session_id == session_id))
        return int(result.scalar_one())

    async def hard_delete_session(self, session_id: UUID) -> int:
        result = await self.session.execute(delete(AttendanceSession).where(AttendanceSession.id == session_id))
        return int(result.rowcount or 0)

    async def archive_session(self, session_id: UUID, deleted_at: datetime) -> AttendanceSession:
        session = await self.get_session_by_id(session_id, include_deleted=True)
        if session is None:
            raise LookupError(f"attendance session {session_id} not found")
        session.is_active = False
        session.is_deleted = True
        session.deleted_at = deleted_at
        await self.session.flush()
        return session

    async def add_log(self, log: AttendanceLog) -> AttendanceLog:
        log.decision = normalize_attendance_decision(log.decision, log.reason)
        log.reason = normalize_attendance_reason(log.reason)
        log.event_type = normalize_attendance_event_type(log.event_type)
        self.session.add(log)
        await self.session.flush()
        return log

    async def has_accepted_log_in_window(
        self,
        session_id: UUID,
        person_id: UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> bool:
        # Prevents the same person from confirming the same session more than
        # once inside a day-shaped window. Uses the accepted decision set so
        # rejection rows do not block re-attempts after a bad scan.
        accepted = list(ATTENDANCE_SUCCESS_DECISIONS)
        result = await self.session.execute(
            select(func.count(AttendanceLog.id))
            .where(
                AttendanceLog.session_id == session_id,
                AttendanceLog.person_id == person_id,
                AttendanceLog.decision.in_(accepted),
                AttendanceLog.is_deleted.is_(False),
                AttendanceLog.created_at >= window_start,
                AttendanceLog.created_at < window_end,
            )
        )
        count = result.scalar_one_or_none() or 0
        return int(count) > 0

    async def clear_matched_templates_for_person(self, person_id: UUID) -> int:
        result = await self.session.execute(
            update(AttendanceLog)
            .where(
                AttendanceLog.person_id == person_id,
                AttendanceLog.matched_template_id.is_not(None),
            )
            .values(matched_template_id=None)
        )
        return int(result.rowcount or 0)

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
            .where(AttendanceSession.session_code == session_code, AttendanceLog.is_deleted.is_(False))
            .order_by(AttendanceLog.created_at.desc())
        )
        return list(result.all())

    async def list_logs_for_session_today(self, session_id, today_start: datetime, today_end: datetime) -> list[tuple[AttendanceLog, Person | None]]:
        result = await self.session.execute(
            select(AttendanceLog, Person)
            .outerjoin(Person, Person.id == AttendanceLog.person_id)
            # Eager-load class_group: the read service touches person.class_group
            # and lazy loading would fail inside the async session.
            .options(joinedload(Person.class_group))
            .where(
                AttendanceLog.session_id == session_id,
                AttendanceLog.is_deleted.is_(False),
                AttendanceLog.created_at >= today_start,
                AttendanceLog.created_at < today_end,
            )
            .order_by(AttendanceLog.created_at.asc())
        )
        return list(result.all())

    async def metrics(self) -> dict[str, int]:
        window_start = datetime.now(timezone.utc) - timedelta(hours=24)
        total_logs = await self.session.execute(select(func.count(AttendanceLog.id)))
        recognized = await self.session.execute(
            select(func.count(AttendanceLog.id)).where(
                AttendanceLog.decision.in_(ATTENDANCE_SUCCESS_DECISIONS),
                AttendanceLog.created_at >= window_start,
            )
        )
        return {
            "total_logs": int(total_logs.scalar_one()),
            "recognized_last_24h": int(recognized.scalar_one()),
        }

    @staticmethod
    def availability_reason(session: AttendanceSession, now: datetime | None = None) -> str | None:
        timestamp = AttendanceRepository._as_utc(now or datetime.now(timezone.utc))
        starts_at = AttendanceRepository._as_utc(session.starts_at)
        ends_at = AttendanceRepository._as_utc(session.ends_at)
        if session.is_deleted:
            return "attendance_session_deleted"
        if not session.is_active:
            return "attendance_session_inactive"
        if session.repeat_days is not None and session.start_time is not None:
            now_wita = timestamp.astimezone(WITA_TZ)
            today_wita = WITA_DAY_NAMES[now_wita.weekday()]
            current_time_wita = now_wita.time()
            if today_wita not in session.repeat_days:
                return "attendance_session_not_scheduled_today"
            if session.start_time is not None and current_time_wita < session.start_time:
                return "attendance_session_not_started"
            if session.end_time is not None and current_time_wita > session.end_time:
                return "attendance_session_ended"
        else:
            if starts_at is not None and timestamp < starts_at:
                return "attendance_session_not_started"
            if ends_at is not None and timestamp > ends_at:
                return "attendance_session_ended"
        return None

    async def _ensure_session_code_available(self, session_code: str, exclude_session_id: UUID | None = None) -> None:
        existing = await self.get_session(session_code, include_deleted=True)
        if existing is None:
            return
        if exclude_session_id is not None and existing.id == exclude_session_id:
            return
        raise ValueError(f"session_code {session_code} already exists")

    async def session_code_exists(self, session_code: str) -> bool:
        return await self.get_session(session_code, include_deleted=True) is not None

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        # None-safe: recurring sessions keep starts_at/ends_at NULL and rely on
        # repeat_days/start_time instead; availability_reason must not crash.
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _projection_from_row(row: tuple[AttendanceSession, int, int, int, int, datetime | None, str | None, str | None, str | None]) -> AttendanceSessionProjection:
        session, total_logs, recognized, cooldown, unknown, last_event_at, class_code, class_name, lecturer_name = row
        return AttendanceSessionProjection(
            session=session,
            total_logs=int(total_logs or 0),
            recognized=int(recognized or 0),
            cooldown=int(cooldown or 0),
            unknown=int(unknown or 0),
            last_event_at=last_event_at,
            class_code=class_code,
            class_name=class_name,
            lecturer_name=lecturer_name,
        )
