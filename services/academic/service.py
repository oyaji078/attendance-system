"""Business logic for jadwal, pertemuan, and manual H/S/I/A attendance.

Authorization note: every method that a lecturer can reach takes an explicit
``lecturer_scope``. When set, the schedule must belong to that lecturer — a guru
cannot open, fill, or recap a class that is not theirs. Passing ``None`` means
"no scoping" and is only ever done for admin callers.
"""

from __future__ import annotations

import logging
from uuid import UUID

from db.repositories.academic import AcademicRepository, MeetingProjection, ScheduleProjection
from db.repositories.attendance import AttendanceRepository
from db.schemas.academic_attendance import (
    AttendanceEntry,
    AttendanceSheetResponse,
    AttendanceSheetStudent,
    ClassScheduleRead,
    ClassScheduleWrite,
    MeetingRead,
    MeetingWrite,
    RecapMeetingColumn,
    RecapResponse,
    RecapRow,
    SubjectRead,
    SubjectWrite,
)
from services.academic.recap import average_percent, held_meeting_count, tally_student

LOGGER = logging.getLogger(__name__)


class AcademicConflictError(ValueError):
    """Duplicate code, or a jadwal that already exists for the same term."""


class AcademicNotFoundError(LookupError):
    pass


class AcademicPermissionError(PermissionError):
    """The signed-in lecturer does not own the schedule they asked for."""


class AcademicService:
    def __init__(
        self,
        repository: AcademicRepository,
        attendance_repository: AttendanceRepository | None = None,
    ) -> None:
        self.repository = repository
        # Only needed for the kiosk-session half of a jadwal; the manual
        # attendance paths work without it.
        self.attendance_repository = attendance_repository

    # ------------------------------------------------------------------ #
    # Mata pelajaran
    # ------------------------------------------------------------------ #

    async def list_subjects(self, *, limit: int = 100, offset: int = 0) -> tuple[list[SubjectRead], int]:
        rows = await self.repository.list_subjects(limit=limit, offset=offset)
        total = await self.repository.count_subjects()
        return [self._subject_read(subject, count) for subject, count in rows], total

    async def create_subject(self, request: SubjectWrite) -> SubjectRead:
        code = request.subject_code or await self.repository.next_subject_code()
        subject = await self.repository.create_subject(
            subject_code=code,
            subject_name=request.subject_name,
            description=request.description,
            is_active=request.is_active,
        )
        return self._subject_read(subject, 0)

    async def update_subject(self, subject_id: UUID, request: SubjectWrite) -> SubjectRead:
        subject = await self.repository.get_subject(subject_id)
        if subject is None:
            raise AcademicNotFoundError("Mata pelajaran tidak ditemukan.")
        # A blank code on update keeps the existing one, matching how the
        # lecturer/class forms already behave.
        subject.subject_code = request.subject_code or subject.subject_code
        subject.subject_name = request.subject_name
        subject.description = request.description
        subject.is_active = request.is_active
        projection = await self.repository.get_subject_with_schedule_count(subject_id)
        count = projection[1] if projection else 0
        return self._subject_read(subject, count)

    async def set_subject_active(self, subject_id: UUID, is_active: bool) -> SubjectRead:
        subject = await self.repository.get_subject(subject_id)
        if subject is None:
            raise AcademicNotFoundError("Mata pelajaran tidak ditemukan.")
        subject.is_active = is_active
        projection = await self.repository.get_subject_with_schedule_count(subject_id)
        return self._subject_read(subject, projection[1] if projection else 0)

    # ------------------------------------------------------------------ #
    # Jadwal
    # ------------------------------------------------------------------ #

    async def list_schedules(
        self,
        *,
        academic_year: str | None = None,
        semester: str | None = None,
        class_id: UUID | None = None,
        subject_id: UUID | None = None,
        lecturer_id: UUID | None = None,
        lecturer_scope: UUID | None = None,
    ) -> list[ClassScheduleRead]:
        # A lecturer's own id always wins over a lecturer_id filter they sent,
        # so the filter cannot be used to peek at another teacher's schedules.
        effective_lecturer = lecturer_scope if lecturer_scope is not None else lecturer_id
        projections = await self.repository.list_schedules(
            academic_year=academic_year,
            semester=semester,
            class_id=class_id,
            subject_id=subject_id,
            lecturer_id=effective_lecturer,
        )
        return [self._schedule_read(item) for item in projections]

    async def get_schedule(self, schedule_id: UUID, *, lecturer_scope: UUID | None = None) -> ClassScheduleRead:
        projection = await self._require_schedule(schedule_id, lecturer_scope)
        return self._schedule_read(projection)

    async def create_schedule(self, request: ClassScheduleWrite) -> ClassScheduleRead:
        code = request.schedule_code or await self.repository.next_schedule_code()
        schedule = await self.repository.create_schedule(
            schedule_code=code,
            class_id=request.class_id,
            subject_id=request.subject_id,
            lecturer_id=request.lecturer_id,
            academic_year=request.academic_year,
            semester=request.semester,
            day_of_week=request.day_of_week,
            start_time=request.start_time,
            end_time=request.end_time,
            total_meetings=request.total_meetings,
            room=request.room,
            is_active=request.is_active,
        )
        if request.with_kiosk_session:
            await self._sync_kiosk_session(schedule, device_code=request.device_code)
        projection = await self.repository.get_schedule_projection(schedule.id)
        if projection is None:
            raise AcademicNotFoundError("Jadwal tidak ditemukan setelah dibuat.")
        return self._schedule_read(projection)

    async def update_schedule(self, schedule_id: UUID, request: ClassScheduleWrite) -> ClassScheduleRead:
        schedule = await self.repository.get_schedule(schedule_id)
        if schedule is None:
            raise AcademicNotFoundError("Jadwal tidak ditemukan.")
        schedule.schedule_code = request.schedule_code or schedule.schedule_code
        schedule.class_id = request.class_id
        schedule.subject_id = request.subject_id
        schedule.lecturer_id = request.lecturer_id
        schedule.academic_year = request.academic_year
        schedule.semester = request.semester
        schedule.day_of_week = request.day_of_week
        schedule.start_time = request.start_time
        schedule.end_time = request.end_time
        schedule.total_meetings = request.total_meetings
        schedule.room = request.room
        schedule.is_active = request.is_active
        # An existing session follows the jadwal it belongs to; a new one is only
        # created when the operator asked for it.
        if request.with_kiosk_session or schedule.attendance_session_id is not None:
            await self._sync_kiosk_session(schedule, device_code=request.device_code)
        projection = await self.repository.get_schedule_projection(schedule_id)
        if projection is None:
            raise AcademicNotFoundError("Jadwal tidak ditemukan setelah diperbarui.")
        return self._schedule_read(projection)

    async def set_schedule_active(self, schedule_id: UUID, is_active: bool) -> ClassScheduleRead:
        schedule = await self.repository.get_schedule(schedule_id)
        if schedule is None:
            raise AcademicNotFoundError("Jadwal tidak ditemukan.")
        schedule.is_active = is_active
        projection = await self.repository.get_schedule_projection(schedule_id)
        if projection is None:
            raise AcademicNotFoundError("Jadwal tidak ditemukan.")
        return self._schedule_read(projection)

    async def delete_schedule(self, schedule_id: UUID) -> dict[str, int | str]:
        """Remove a jadwal along with its meetings and attendance.

        This is a hard delete because a jadwal owns its meetings and their
        H/S/I/A records (ON DELETE CASCADE) — leaving orphan attendance for a
        schedule nobody can open would quietly skew every recap. The kiosk
        session it owns is kept and only unlinked: face-recognition logs point
        at it, and those are the audit trail.
        """
        projection = await self.repository.get_schedule_projection(schedule_id)
        if projection is None:
            raise AcademicNotFoundError("Jadwal tidak ditemukan.")
        counts = await self.repository.count_schedule_dependents(schedule_id)
        session_id = projection.schedule.attendance_session_id
        if session_id is not None and self.attendance_repository is not None:
            kiosk_session = await self.attendance_repository.get_session_by_id(session_id)
            if kiosk_session is not None:
                kiosk_session.is_active = False
            projection.schedule.attendance_session_id = None
        await self.repository.delete_schedule(schedule_id)
        LOGGER.info(
            "schedule_deleted",
            extra={
                "schedule_id": str(schedule_id),
                "meetings_deleted": counts["meetings"],
                "records_deleted": counts["records"],
            },
        )
        return {
            "status": "deleted",
            "meetings_deleted": counts["meetings"],
            "records_deleted": counts["records"],
            "detail": (
                f"Jadwal {projection.schedule.schedule_code} dihapus beserta "
                f"{counts['meetings']} pertemuan dan {counts['records']} data absensi."
            ),
        }

    async def list_academic_years(self) -> list[str]:
        return await self.repository.list_academic_years()

    async def ensure_kiosk_session(
        self, schedule_id: UUID, *, device_code: str | None = None, lecturer_scope: UUID | None = None
    ) -> ClassScheduleRead:
        """Create the jadwal's kiosk session, or refresh it if it already has one."""
        projection = await self._require_schedule(schedule_id, lecturer_scope)
        await self._sync_kiosk_session(projection.schedule, device_code=device_code)
        refreshed = await self.repository.get_schedule_projection(schedule_id)
        return self._schedule_read(refreshed or projection)

    async def set_kiosk_session_active(
        self, schedule_id: UUID, is_active: bool, *, lecturer_scope: UUID | None = None
    ) -> ClassScheduleRead:
        projection = await self._require_schedule(schedule_id, lecturer_scope)
        if projection.schedule.attendance_session_id is None:
            raise AcademicNotFoundError("Jadwal ini belum punya sesi absensi wajah.")
        if self.attendance_repository is None:
            raise AcademicNotFoundError("Layanan sesi absensi tidak tersedia.")
        session = await self.attendance_repository.get_session_by_id(projection.schedule.attendance_session_id)
        if session is None:
            raise AcademicNotFoundError("Sesi absensi tidak ditemukan.")
        session.is_active = is_active
        refreshed = await self.repository.get_schedule_projection(schedule_id)
        return self._schedule_read(refreshed or projection)

    async def _sync_kiosk_session(self, schedule, *, device_code: str | None = None) -> None:
        """Create or update the AttendanceSession that mirrors this jadwal.

        The kiosk decides availability from ``repeat_days`` + ``start_time`` +
        ``end_time``, and its validator requires all three together — so a jadwal
        without a day/time produces an always-available session instead of an
        invalid one.
        """
        if self.attendance_repository is None:
            raise AcademicNotFoundError("Layanan sesi absensi tidak tersedia.")

        recurring = bool(schedule.day_of_week and schedule.start_time and schedule.end_time)
        repeat_days = [schedule.day_of_week] if recurring else None
        start_time = schedule.start_time if recurring else None
        end_time = schedule.end_time if recurring else None
        name = f"{schedule.schedule_code} - {schedule.academic_year} {schedule.semester}"

        existing_id = schedule.attendance_session_id
        if existing_id is not None:
            session = await self.attendance_repository.get_session_by_id(existing_id)
            if session is not None and not session.is_deleted:
                session.session_name = name
                session.class_id = schedule.class_id
                session.lecturer_id = schedule.lecturer_id
                session.repeat_days = repeat_days
                session.start_time = start_time
                session.end_time = end_time
                if device_code:
                    session.device_code = device_code
                return
            # The session was deleted out from under the jadwal: build a new one.
            schedule.attendance_session_id = None

        session = await self.attendance_repository.create_session(
            session_code=await self._next_session_code(),
            session_name=name,
            session_kind="lecture",
            class_id=schedule.class_id,
            lecturer_id=schedule.lecturer_id,
            device_code=device_code,
            cooldown_seconds=30,
            starts_at=None,
            ends_at=None,
            is_active=True,
            repeat_days=repeat_days,
            start_time=start_time,
            end_time=end_time,
            tz="Asia/Makassar",
        )
        schedule.attendance_session_id = session.id
        LOGGER.info(
            "jadwal_kiosk_session_linked",
            extra={"schedule_id": str(schedule.id), "session_code": session.session_code},
        )

    async def _next_session_code(self) -> str:
        # Reuse the existing generator so jadwal-owned sessions get exactly the
        # same ABS-YYMMDD-HHMM-NNNN codes as hand-made ones.
        from services.attendance.session_service import AttendanceSessionService

        return await AttendanceSessionService(self.attendance_repository).next_session_code()

    # ------------------------------------------------------------------ #
    # Pertemuan
    # ------------------------------------------------------------------ #

    async def list_meetings(
        self, schedule_id: UUID, *, lecturer_scope: UUID | None = None
    ) -> tuple[ClassScheduleRead, list[MeetingRead]]:
        projection = await self._require_schedule(schedule_id, lecturer_scope)
        meetings = await self.repository.list_meetings(schedule_id)
        return self._schedule_read(projection), [self._meeting_read(item) for item in meetings]

    async def generate_meetings(
        self, schedule_id: UUID, *, total_meetings: int | None = None, lecturer_scope: UUID | None = None
    ) -> tuple[ClassScheduleRead, list[MeetingRead]]:
        """Create the missing meetings 1..N. Existing ones are never touched.

        N comes from the request, or from the schedule's own ``total_meetings``
        (default 12) — the count is data, so a term of 8 or 16 meetings needs no
        code change.
        """
        projection = await self._require_schedule(schedule_id, lecturer_scope)
        schedule = projection.schedule
        target = total_meetings or schedule.total_meetings or 12
        if total_meetings and total_meetings != schedule.total_meetings:
            schedule.total_meetings = total_meetings
        existing = await self.repository.existing_meeting_numbers(schedule_id)
        missing = [number for number in range(1, target + 1) if number not in existing]
        if missing:
            await self.repository.add_meetings(schedule_id, missing)
        refreshed = await self.repository.get_schedule_projection(schedule_id)
        meetings = await self.repository.list_meetings(schedule_id)
        # NOTE: "created"/"message"/"module" and friends are reserved LogRecord
        # attributes; using them in `extra` raises KeyError at log time.
        LOGGER.info(
            "schedule_meetings_generated",
            extra={"schedule_id": str(schedule_id), "created_count": len(missing), "target_count": target},
        )
        return self._schedule_read(refreshed or projection), [self._meeting_read(item) for item in meetings]

    async def update_meeting(
        self, meeting_id: UUID, request: MeetingWrite, *, lecturer_scope: UUID | None = None
    ) -> MeetingRead:
        meeting = await self.repository.get_meeting(meeting_id)
        if meeting is None:
            raise AcademicNotFoundError("Pertemuan tidak ditemukan.")
        await self._require_schedule(meeting.schedule_id, lecturer_scope)
        meeting.meeting_date = request.meeting_date
        meeting.topic = request.topic
        meeting.status = request.status
        meeting.attendance_session_id = request.attendance_session_id
        meeting.notes = request.notes
        projection = await self.repository.get_meeting_projection(meeting_id)
        if projection is None:
            raise AcademicNotFoundError("Pertemuan tidak ditemukan.")
        return self._meeting_read(projection)

    # ------------------------------------------------------------------ #
    # Input absensi
    # ------------------------------------------------------------------ #

    async def attendance_sheet(
        self, meeting_id: UUID, *, lecturer_scope: UUID | None = None
    ) -> AttendanceSheetResponse:
        """Every student of the meeting's class, with any status already saved."""
        meeting_projection = await self.repository.get_meeting_projection(meeting_id)
        if meeting_projection is None:
            raise AcademicNotFoundError("Pertemuan tidak ditemukan.")
        schedule_projection = await self._require_schedule(meeting_projection.meeting.schedule_id, lecturer_scope)

        students = await self.repository.list_class_students(schedule_projection.schedule.class_id)
        records = {record.person_id: record for record in await self.repository.list_records_for_meeting(meeting_id)}
        rows: list[AttendanceSheetStudent] = []
        for index, person in enumerate(students, start=1):
            record = records.get(person.id)
            rows.append(
                AttendanceSheetStudent(
                    no=index,
                    person_id=person.id,
                    student_id=person.student_id,
                    full_name=person.full_name,
                    address=person.address,
                    status=record.status if record else None,
                    note=record.note if record else None,
                    source=record.source if record else None,
                    updated_at=record.updated_at if record else None,
                )
            )
        return AttendanceSheetResponse(
            schedule=self._schedule_read(schedule_projection),
            meeting=self._meeting_read(meeting_projection),
            students=rows,
            student_count=len(rows),
        )

    async def save_attendance(
        self,
        meeting_id: UUID,
        entries: list[AttendanceEntry],
        *,
        mark_meeting_held: bool = True,
        recorded_by_admin_id: UUID | None = None,
        lecturer_scope: UUID | None = None,
    ) -> tuple[int, int, int]:
        """Upsert one status per student. Returns (created, updated, skipped)."""
        meeting = await self.repository.get_meeting(meeting_id)
        if meeting is None:
            raise AcademicNotFoundError("Pertemuan tidak ditemukan.")
        schedule_projection = await self._require_schedule(meeting.schedule_id, lecturer_scope)

        # Only students of this meeting's class may be graded here; anything
        # else in the payload is dropped rather than silently written.
        allowed = {person.id for person in await self.repository.list_class_students(schedule_projection.schedule.class_id)}
        accepted: dict[UUID, tuple[str, str | None]] = {}
        skipped = 0
        for entry in entries:
            if entry.person_id not in allowed:
                skipped += 1
                continue
            accepted[entry.person_id] = (entry.status, entry.note)

        created, updated = await self.repository.upsert_records(
            meeting_id=meeting_id,
            entries=accepted,
            recorded_by_admin_id=recorded_by_admin_id,
        )
        if mark_meeting_held and accepted and meeting.status == "planned":
            # Saving a sheet is the act that makes a meeting "sudah dilaksanakan",
            # which is what the percentage denominator counts.
            meeting.status = "held"
        LOGGER.info(
            "attendance_records_saved",
            extra={
                "meeting_id": str(meeting_id),
                "created_count": created,
                "updated_count": updated,
                "skipped_count": skipped,
            },
        )
        return created, updated, skipped

    # ------------------------------------------------------------------ #
    # Rekap
    # ------------------------------------------------------------------ #

    async def recap(self, schedule_id: UUID, *, lecturer_scope: UUID | None = None) -> RecapResponse:
        projection = await self._require_schedule(schedule_id, lecturer_scope)
        meetings = await self.repository.list_meetings(schedule_id)
        students = await self.repository.list_class_students(projection.schedule.class_id)

        meeting_ids = [item.meeting.id for item in meetings]
        by_person: dict[UUID, dict[UUID, str]] = {}
        for record in await self.repository.list_records_for_meetings(meeting_ids):
            by_person.setdefault(record.person_id, {})[record.meeting_id] = record.status

        columns = [
            RecapMeetingColumn(
                meeting_id=item.meeting.id,
                meeting_number=item.meeting.meeting_number,
                meeting_date=item.meeting.meeting_date,
                status=item.meeting.status,
                label=str(item.meeting.meeting_number),
            )
            for item in meetings
        ]
        meeting_statuses = [item.meeting.status for item in meetings]

        rows: list[RecapRow] = []
        for index, person in enumerate(students, start=1):
            person_records = by_person.get(person.id, {})
            cells = [person_records.get(item.meeting.id) for item in meetings]
            tally = tally_student(cells, meeting_statuses)
            rows.append(
                RecapRow(
                    no=index,
                    person_id=person.id,
                    student_id=person.student_id,
                    full_name=person.full_name,
                    cells=cells,
                    hadir=tally.hadir,
                    sakit=tally.sakit,
                    izin=tally.izin,
                    alpha=tally.alpha,
                    held_meetings=tally.held_meetings,
                    attendance_percent=tally.attendance_percent,
                )
            )

        return RecapResponse(
            schedule=self._schedule_read(projection),
            columns=columns,
            rows=rows,
            student_count=len(rows),
            total_meetings=len(meetings),
            held_meetings=held_meeting_count(meeting_statuses),
            average_percent=average_percent([row.attendance_percent for row in rows]),
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    async def _require_schedule(self, schedule_id: UUID, lecturer_scope: UUID | None) -> ScheduleProjection:
        projection = await self.repository.get_schedule_projection(schedule_id)
        if projection is None:
            raise AcademicNotFoundError("Jadwal tidak ditemukan.")
        if lecturer_scope is not None and projection.schedule.lecturer_id != lecturer_scope:
            raise AcademicPermissionError("Jadwal ini bukan milik akun guru yang sedang masuk.")
        return projection

    @staticmethod
    def _subject_read(subject, schedule_count: int) -> SubjectRead:
        return SubjectRead(
            subject_id=subject.id,
            subject_code=subject.subject_code,
            subject_name=subject.subject_name,
            description=subject.description,
            is_active=subject.is_active,
            schedule_count=schedule_count,
            created_at=subject.created_at,
            updated_at=subject.updated_at,
        )

    @staticmethod
    def _schedule_read(projection: ScheduleProjection) -> ClassScheduleRead:
        schedule = projection.schedule
        return ClassScheduleRead(
            schedule_id=schedule.id,
            schedule_code=schedule.schedule_code,
            class_id=schedule.class_id,
            class_code=projection.class_code,
            class_name=projection.class_name,
            subject_id=schedule.subject_id,
            subject_code=projection.subject_code,
            subject_name=projection.subject_name,
            lecturer_id=schedule.lecturer_id,
            lecturer_name=projection.lecturer_name,
            academic_year=schedule.academic_year,
            semester=schedule.semester,
            day_of_week=schedule.day_of_week,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            total_meetings=schedule.total_meetings,
            room=schedule.room,
            is_active=schedule.is_active,
            attendance_session_id=schedule.attendance_session_id,
            session_code=projection.session_code,
            session_name=projection.session_name,
            session_is_active=projection.session_is_active,
            student_count=projection.student_count,
            meeting_count=projection.meeting_count,
            held_meeting_count=projection.held_meeting_count,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )

    @staticmethod
    def _meeting_read(projection: MeetingProjection) -> MeetingRead:
        meeting = projection.meeting
        return MeetingRead(
            meeting_id=meeting.id,
            schedule_id=meeting.schedule_id,
            meeting_number=meeting.meeting_number,
            meeting_date=meeting.meeting_date,
            topic=meeting.topic,
            status=meeting.status,
            attendance_session_id=meeting.attendance_session_id,
            notes=meeting.notes,
            recorded_count=projection.recorded_count,
            present_count=projection.present_count,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
        )
