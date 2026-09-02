"""Queries for jadwal, pertemuan, and manual H/S/I/A attendance.

All statements go through SQLAlchemy Core/ORM constructs (bound parameters), so
values from request bodies and query strings never reach the database as SQL
text — same posture as the existing repositories.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type, time
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import (
    AttendanceRecord,
    AttendanceSession,
    ClassGroup,
    ClassSchedule,
    Lecturer,
    Person,
    ScheduleMeeting,
    Subject,
)


@dataclass(slots=True)
class ScheduleProjection:
    schedule: ClassSchedule
    class_code: str | None
    class_name: str | None
    subject_code: str | None
    subject_name: str | None
    lecturer_name: str | None
    student_count: int
    meeting_count: int
    held_meeting_count: int
    session_code: str | None = None
    session_name: str | None = None
    session_is_active: bool | None = None


@dataclass(slots=True)
class MeetingProjection:
    meeting: ScheduleMeeting
    recorded_count: int
    present_count: int


class AcademicRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    # Subjects
    # ------------------------------------------------------------------ #

    async def list_subjects(self, *, include_inactive: bool = True, limit: int = 100, offset: int = 0) -> list[tuple[Subject, int]]:
        statement = (
            select(Subject, func.count(ClassSchedule.id))
            .outerjoin(ClassSchedule, ClassSchedule.subject_id == Subject.id)
            .group_by(Subject.id)
            .order_by(Subject.subject_code.asc())
            .offset(offset)
            .limit(limit)
        )
        if not include_inactive:
            statement = statement.where(Subject.is_active.is_(True))
        result = await self.session.execute(statement)
        return [(row[0], int(row[1] or 0)) for row in result.all()]

    async def count_subjects(self, *, include_inactive: bool = True) -> int:
        statement = select(func.count(Subject.id))
        if not include_inactive:
            statement = statement.where(Subject.is_active.is_(True))
        result = await self.session.execute(statement)
        return int(result.scalar_one())

    async def get_subject(self, subject_id: UUID) -> Subject | None:
        return await self.session.get(Subject, subject_id)

    async def get_subject_with_schedule_count(self, subject_id: UUID) -> tuple[Subject, int] | None:
        result = await self.session.execute(
            select(Subject, func.count(ClassSchedule.id))
            .outerjoin(ClassSchedule, ClassSchedule.subject_id == Subject.id)
            .where(Subject.id == subject_id)
            .group_by(Subject.id)
        )
        row = result.one_or_none()
        return None if row is None else (row[0], int(row[1] or 0))

    async def next_subject_code(self) -> str:
        return await self._next_sequential_code(Subject.subject_code, "MAPEL")

    async def create_subject(self, **values) -> Subject:
        subject = Subject(**values)
        self.session.add(subject)
        await self.session.flush()
        return subject

    # ------------------------------------------------------------------ #
    # Schedules
    # ------------------------------------------------------------------ #

    @staticmethod
    def _schedule_projection_statement() -> Select:
        # Correlated scalar subqueries instead of extra joins: joining students
        # and meetings at once multiplies rows and inflates both counts.
        student_count = (
            select(func.count(Person.id))
            .where(Person.class_id == ClassSchedule.class_id, Person.is_deleted.is_(False))
            .correlate(ClassSchedule)
            .scalar_subquery()
        )
        meeting_count = (
            select(func.count(ScheduleMeeting.id))
            .where(ScheduleMeeting.schedule_id == ClassSchedule.id)
            .correlate(ClassSchedule)
            .scalar_subquery()
        )
        held_count = (
            select(func.count(ScheduleMeeting.id))
            .where(ScheduleMeeting.schedule_id == ClassSchedule.id, ScheduleMeeting.status == "held")
            .correlate(ClassSchedule)
            .scalar_subquery()
        )
        return (
            select(
                ClassSchedule,
                ClassGroup.class_code,
                ClassGroup.class_name,
                Subject.subject_code,
                Subject.subject_name,
                Lecturer.full_name,
                student_count.label("student_count"),
                meeting_count.label("meeting_count"),
                held_count.label("held_meeting_count"),
                AttendanceSession.session_code,
                AttendanceSession.session_name,
                AttendanceSession.is_active,
            )
            .join(ClassGroup, ClassGroup.id == ClassSchedule.class_id)
            .join(Subject, Subject.id == ClassSchedule.subject_id)
            .outerjoin(Lecturer, Lecturer.id == ClassSchedule.lecturer_id)
            .outerjoin(
                AttendanceSession,
                (AttendanceSession.id == ClassSchedule.attendance_session_id)
                & (AttendanceSession.is_deleted.is_(False)),
            )
        )

    @staticmethod
    def _row_to_schedule_projection(row) -> ScheduleProjection:
        (
            schedule,
            class_code,
            class_name,
            subject_code,
            subject_name,
            lecturer_name,
            students,
            meetings,
            held,
            session_code,
            session_name,
            session_is_active,
        ) = row
        return ScheduleProjection(
            schedule=schedule,
            class_code=class_code,
            class_name=class_name,
            subject_code=subject_code,
            subject_name=subject_name,
            lecturer_name=lecturer_name,
            student_count=int(students or 0),
            meeting_count=int(meetings or 0),
            held_meeting_count=int(held or 0),
            session_code=session_code,
            session_name=session_name,
            session_is_active=session_is_active,
        )

    async def list_schedules(
        self,
        *,
        academic_year: str | None = None,
        semester: str | None = None,
        class_id: UUID | None = None,
        subject_id: UUID | None = None,
        lecturer_id: UUID | None = None,
        include_inactive: bool = True,
    ) -> list[ScheduleProjection]:
        statement = self._schedule_projection_statement()
        if academic_year:
            statement = statement.where(ClassSchedule.academic_year == academic_year)
        if semester:
            statement = statement.where(ClassSchedule.semester == semester)
        if class_id is not None:
            statement = statement.where(ClassSchedule.class_id == class_id)
        if subject_id is not None:
            statement = statement.where(ClassSchedule.subject_id == subject_id)
        if lecturer_id is not None:
            statement = statement.where(ClassSchedule.lecturer_id == lecturer_id)
        if not include_inactive:
            statement = statement.where(ClassSchedule.is_active.is_(True))
        statement = statement.order_by(
            ClassSchedule.academic_year.desc(),
            ClassSchedule.semester.asc(),
            ClassGroup.class_code.asc(),
            Subject.subject_code.asc(),
        )
        result = await self.session.execute(statement)
        return [self._row_to_schedule_projection(row) for row in result.all()]

    async def get_schedule_projection(self, schedule_id: UUID) -> ScheduleProjection | None:
        result = await self.session.execute(
            self._schedule_projection_statement().where(ClassSchedule.id == schedule_id)
        )
        row = result.one_or_none()
        return None if row is None else self._row_to_schedule_projection(row)

    async def get_schedule(self, schedule_id: UUID) -> ClassSchedule | None:
        return await self.session.get(ClassSchedule, schedule_id)

    async def next_schedule_code(self) -> str:
        return await self._next_sequential_code(ClassSchedule.schedule_code, "JDW")

    async def create_schedule(self, **values) -> ClassSchedule:
        schedule = ClassSchedule(**values)
        self.session.add(schedule)
        await self.session.flush()
        return schedule

    async def list_unlinked_session_ids(self) -> set[UUID]:
        result = await self.session.execute(
            select(ClassSchedule.attendance_session_id).where(ClassSchedule.attendance_session_id.isnot(None))
        )
        return {value for value in result.scalars().all() if value is not None}

    async def count_schedule_dependents(self, schedule_id: UUID) -> dict[str, int]:
        """How much data a delete would take with it, for the confirmation."""
        meetings = int((await self.session.execute(
            select(func.count(ScheduleMeeting.id)).where(ScheduleMeeting.schedule_id == schedule_id)
        )).scalar_one())
        records = int((await self.session.execute(
            select(func.count(AttendanceRecord.id))
            .join(ScheduleMeeting, ScheduleMeeting.id == AttendanceRecord.meeting_id)
            .where(ScheduleMeeting.schedule_id == schedule_id)
        )).scalar_one())
        return {"meetings": meetings, "records": records}

    async def delete_schedule(self, schedule_id: UUID) -> None:
        schedule = await self.session.get(ClassSchedule, schedule_id)
        if schedule is not None:
            # Meetings and attendance_records go with it via ON DELETE CASCADE.
            await self.session.delete(schedule)
            await self.session.flush()

    async def list_academic_years(self) -> list[str]:
        result = await self.session.execute(
            select(ClassSchedule.academic_year).distinct().order_by(ClassSchedule.academic_year.desc())
        )
        return [value for value in result.scalars().all() if value]

    # ------------------------------------------------------------------ #
    # Meetings
    # ------------------------------------------------------------------ #

    @staticmethod
    def _meeting_projection_statement() -> Select:
        recorded = (
            select(func.count(AttendanceRecord.id))
            .where(AttendanceRecord.meeting_id == ScheduleMeeting.id)
            .correlate(ScheduleMeeting)
            .scalar_subquery()
        )
        present = (
            select(func.count(AttendanceRecord.id))
            .where(AttendanceRecord.meeting_id == ScheduleMeeting.id, AttendanceRecord.status == "H")
            .correlate(ScheduleMeeting)
            .scalar_subquery()
        )
        return select(ScheduleMeeting, recorded.label("recorded_count"), present.label("present_count"))

    async def list_meetings(self, schedule_id: UUID) -> list[MeetingProjection]:
        result = await self.session.execute(
            self._meeting_projection_statement()
            .where(ScheduleMeeting.schedule_id == schedule_id)
            .order_by(ScheduleMeeting.meeting_number.asc())
        )
        return [MeetingProjection(meeting=row[0], recorded_count=int(row[1] or 0), present_count=int(row[2] or 0)) for row in result.all()]

    async def get_meeting_projection(self, meeting_id: UUID) -> MeetingProjection | None:
        result = await self.session.execute(
            self._meeting_projection_statement().where(ScheduleMeeting.id == meeting_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return MeetingProjection(meeting=row[0], recorded_count=int(row[1] or 0), present_count=int(row[2] or 0))

    async def get_meeting(self, meeting_id: UUID) -> ScheduleMeeting | None:
        return await self.session.get(ScheduleMeeting, meeting_id)

    async def existing_meeting_numbers(self, schedule_id: UUID) -> set[int]:
        result = await self.session.execute(
            select(ScheduleMeeting.meeting_number).where(ScheduleMeeting.schedule_id == schedule_id)
        )
        return {int(value) for value in result.scalars().all()}

    async def add_meetings(self, schedule_id: UUID, numbers: list[int]) -> list[ScheduleMeeting]:
        meetings = [ScheduleMeeting(schedule_id=schedule_id, meeting_number=number, status="planned") for number in numbers]
        self.session.add_all(meetings)
        await self.session.flush()
        return meetings

    # ------------------------------------------------------------------ #
    # Students and attendance records
    # ------------------------------------------------------------------ #

    async def list_class_students(self, class_id: UUID) -> list[Person]:
        result = await self.session.execute(
            select(Person)
            .where(Person.class_id == class_id, Person.is_deleted.is_(False))
            .order_by(Person.student_id.asc(), Person.full_name.asc())
        )
        return list(result.scalars().all())

    async def list_records_for_meeting(self, meeting_id: UUID) -> list[AttendanceRecord]:
        result = await self.session.execute(
            select(AttendanceRecord).where(AttendanceRecord.meeting_id == meeting_id)
        )
        return list(result.scalars().all())

    async def list_records_for_meetings(self, meeting_ids: list[UUID]) -> list[AttendanceRecord]:
        if not meeting_ids:
            return []
        result = await self.session.execute(
            select(AttendanceRecord).where(AttendanceRecord.meeting_id.in_(meeting_ids))
        )
        return list(result.scalars().all())

    async def upsert_records(
        self,
        *,
        meeting_id: UUID,
        entries: dict[UUID, tuple[str, str | None]],
        recorded_by_admin_id: UUID | None,
        source: str = "manual",
    ) -> tuple[int, int]:
        """Insert or update one row per (meeting, person). Returns (created, updated).

        Updating in place is what keeps Pertemuan 1 from being overwritten by a
        later save and what keeps the table free of duplicate rows; the unique
        constraint on (meeting_id, person_id) is the backstop.
        """
        existing = {record.person_id: record for record in await self.list_records_for_meeting(meeting_id)}
        created = 0
        updated = 0
        for person_id, (status, note) in entries.items():
            record = existing.get(person_id)
            if record is None:
                self.session.add(
                    AttendanceRecord(
                        meeting_id=meeting_id,
                        person_id=person_id,
                        status=status,
                        note=note,
                        source=source,
                        recorded_by_admin_id=recorded_by_admin_id,
                    )
                )
                created += 1
                continue
            if record.status != status or record.note != note:
                record.status = status
                record.note = note
                record.source = source
                record.recorded_by_admin_id = recorded_by_admin_id
                if source == "manual":
                    record.match_score = None
                updated += 1
        await self.session.flush()
        return created, updated

    async def _next_sequential_code(self, column, prefix: str) -> str:
        import re

        result = await self.session.execute(select(column).where(column.like(f"{prefix}-%")))
        used: set[int] = set()
        for value in result.scalars().all():
            match = re.search(r"-(\d+)$", value or "")
            if match:
                used.add(int(match.group(1)))
        candidate = 1
        while candidate in used:
            candidate += 1
        return f"{prefix}-{candidate:04d}"
