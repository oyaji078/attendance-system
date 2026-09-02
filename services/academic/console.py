"""Read/write logic behind the redesigned admin console.

Everything a console page shows is derived here rather than in the browser: the
recap percentages, the dashboard counts, the per-student summaries. The frontend
renders what it is given.
"""

from __future__ import annotations

from datetime import date as date_type, datetime, timedelta, timezone
import logging
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.domain.attendance import ATTENDANCE_SUCCESS_DECISIONS
from db.models.entities import (
    AppSetting,
    AttendanceLog,
    AttendanceRecord,
    ClassGroup,
    ClassSchedule,
    Lecturer,
    Person,
    ScheduleMeeting,
    StudentEnrollment,
    Subject,
)
from db.schemas.console import (
    AttendanceEventRow,
    ClassDetailResponse,
    ClassRecapResponse,
    ClassRecapRow,
    ClassRecapSubject,
    ClassStudentRow,
    DashboardAccuracy,
    DashboardActivity,
    DashboardMetric,
    DashboardResponse,
    EnrollmentRead,
    EnrollmentWrite,
    SettingsPayload,
    SettingsResponse,
    StudentDetailResponse,
    StudentSubjectSummary,
)
from services.academic.recap import attendance_percent

LOGGER = logging.getLogger(__name__)

WITA_TZ = timezone(timedelta(hours=8))

SETTING_KEYS = ("school_name", "default_academic_year", "default_semester", "school_logo")


def wita_today() -> date_type:
    return datetime.now(timezone.utc).astimezone(WITA_TZ).date()


# A match under this is worth a second look even though the camera accepted it:
# it is the confidence the kiosk normally demands, so anything below only got
# through on a device configured more loosely.
WEAK_MATCH_SCORE = 0.55


def face_accuracy_summary(scores: list[float | None]) -> tuple[float | None, float | None, int]:
    """(average, lowest, how many are weak) over the match scores given.

    Rows without a score are ignored rather than counted as zero: a manual
    correction has no face behind it, and averaging it in would report the
    camera as less certain than it was.
    """
    known = [float(score) for score in scores if score is not None]
    if not known:
        return None, None, 0
    average = round(sum(known) / len(known), 4)
    weak = sum(1 for score in known if score < WEAK_MATCH_SCORE)
    return average, min(known), weak


class ConsoleNotFoundError(LookupError):
    pass


class ConsoleConflictError(ValueError):
    pass


class ConsoleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    # Dashboard
    # ------------------------------------------------------------------ #

    async def dashboard(self) -> DashboardResponse:
        today = wita_today()

        total_students = int((await self.session.execute(
            select(func.count(Person.id)).where(Person.is_deleted.is_(False))
        )).scalar_one())
        active_classes = int((await self.session.execute(
            select(func.count(ClassGroup.id)).where(ClassGroup.is_active.is_(True))
        )).scalar_one())
        enrolled_faces = int((await self.session.execute(
            select(func.count(Person.id)).where(Person.is_deleted.is_(False), Person.primary_template_id.isnot(None))
        )).scalar_one())

        # Today's attendance comes from the H/S/I/A ledger, which is what the
        # recap reports; the kiosk feeds it through the meeting sheet.
        status_rows = await self.session.execute(
            select(AttendanceRecord.status, func.count(AttendanceRecord.id))
            .join(ScheduleMeeting, ScheduleMeeting.id == AttendanceRecord.meeting_id)
            .where(ScheduleMeeting.meeting_date == today)
            .group_by(AttendanceRecord.status)
        )
        by_status = {row[0]: int(row[1]) for row in status_rows.all()}
        present = by_status.get("H", 0)
        absent = by_status.get("A", 0) + by_status.get("S", 0) + by_status.get("I", 0)

        metrics = [
            DashboardMetric(key="students", label="Total Siswa", value=total_students),
            DashboardMetric(key="classes", label="Kelas Aktif", value=active_classes),
            DashboardMetric(
                key="present_today", label="Hadir Hari Ini", value=present,
                hint=None if present or absent else "Belum ada pertemuan hari ini",
            ),
            DashboardMetric(key="absent_today", label="Tidak Hadir Hari Ini", value=absent),
        ]

        # How sure the camera was about what it filed. Today when the camera has
        # been used today, otherwise the last day it was: a school that is not
        # scanning this hour still needs to see how recognition is holding up,
        # and a card that blanks out every quiet morning tells them nothing.
        score_day = (await self.session.execute(
            select(func.max(ScheduleMeeting.meeting_date))
            .select_from(AttendanceRecord)
            .join(ScheduleMeeting, ScheduleMeeting.id == AttendanceRecord.meeting_id)
            .where(
                ScheduleMeeting.meeting_date <= today,
                AttendanceRecord.source == "face",
                AttendanceRecord.match_score.isnot(None),
            )
        )).scalar()

        scores: list[float | None] = []
        if score_day is not None:
            # Scored rows only: a hand-entered status carries no match to average.
            score_rows = await self.session.execute(
                select(AttendanceRecord.match_score)
                .join(ScheduleMeeting, ScheduleMeeting.id == AttendanceRecord.meeting_id)
                .where(
                    ScheduleMeeting.meeting_date == score_day,
                    AttendanceRecord.source == "face",
                    AttendanceRecord.match_score.isnot(None),
                )
            )
            scores = [row[0] for row in score_rows.all()]

        average_score, lowest_score, weak_scores = face_accuracy_summary(scores)
        accuracy = DashboardAccuracy(
            date=score_day,
            scored=len(scores),
            average=average_score,
            lowest=lowest_score,
            weak=weak_scores,
            threshold=WEAK_MATCH_SCORE,
        )

        activity_rows = await self.session.execute(
            select(
                AttendanceRecord.updated_at,
                Person.full_name,
                Person.student_id,
                ClassGroup.class_code,
                Subject.subject_name,
                AttendanceRecord.status,
                AttendanceRecord.source,
                AttendanceRecord.match_score,
            )
            .join(ScheduleMeeting, ScheduleMeeting.id == AttendanceRecord.meeting_id)
            .join(ClassSchedule, ClassSchedule.id == ScheduleMeeting.schedule_id)
            .join(Subject, Subject.id == ClassSchedule.subject_id)
            .join(ClassGroup, ClassGroup.id == ClassSchedule.class_id)
            .join(Person, Person.id == AttendanceRecord.person_id)
            .order_by(AttendanceRecord.updated_at.desc())
            .limit(12)
        )
        activity = [
            DashboardActivity(
                at=row[0], student_name=row[1], student_id=row[2], class_code=row[3],
                subject_name=row[4], status=row[5], source=row[6] if row[6] in ("face", "manual") else "manual",
                match_score=row[7],
            )
            for row in activity_rows.all()
        ]

        return DashboardResponse(
            metrics=metrics,
            today_present=present,
            today_absent=absent,
            today_total=present + absent,
            accuracy=accuracy,
            activity=activity,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------ #
    # Monitoring absensi
    # ------------------------------------------------------------------ #

    def _attendance_event_statement(
        self,
        *,
        on_date: date_type | None,
        class_id: UUID | None,
        subject_id: UUID | None,
        status: str | None,
        source: str | None,
    ):
        statement = (
            select(
                AttendanceRecord.id,
                ScheduleMeeting.meeting_date,
                ClassGroup.class_code,
                ClassGroup.class_name,
                Subject.subject_code,
                Subject.subject_name,
                ScheduleMeeting.meeting_number,
                ClassSchedule.start_time,
                ClassSchedule.end_time,
                Person.student_id,
                Person.full_name,
                Person.id,
                AttendanceRecord.status,
                AttendanceRecord.updated_at,
                AttendanceRecord.source,
                AttendanceRecord.match_score,
            )
            .join(ScheduleMeeting, ScheduleMeeting.id == AttendanceRecord.meeting_id)
            .join(ClassSchedule, ClassSchedule.id == ScheduleMeeting.schedule_id)
            .join(Subject, Subject.id == ClassSchedule.subject_id)
            .join(ClassGroup, ClassGroup.id == ClassSchedule.class_id)
            .join(Person, Person.id == AttendanceRecord.person_id)
        )
        if on_date is not None:
            statement = statement.where(ScheduleMeeting.meeting_date == on_date)
        if class_id is not None:
            statement = statement.where(ClassSchedule.class_id == class_id)
        if subject_id is not None:
            statement = statement.where(ClassSchedule.subject_id == subject_id)
        if status:
            statement = statement.where(AttendanceRecord.status == status)
        if source:
            statement = statement.where(AttendanceRecord.source == source)
        return statement

    async def attendance_events(
        self,
        *,
        on_date: date_type | None = None,
        class_id: UUID | None = None,
        subject_id: UUID | None = None,
        status: str | None = None,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AttendanceEventRow], int]:
        base = self._attendance_event_statement(
            on_date=on_date, class_id=class_id, subject_id=subject_id, status=status, source=source
        )
        total = int((await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one())

        result = await self.session.execute(
            base.order_by(ScheduleMeeting.meeting_date.desc().nullslast(), AttendanceRecord.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = [
            AttendanceEventRow(
                no=offset + index,
                record_id=row[0], date=row[1], class_code=row[2], class_name=row[3],
                subject_code=row[4], subject_name=row[5], meeting_number=row[6],
                start_time=row[7], end_time=row[8], student_id=row[9], student_name=row[10],
                person_id=row[11], status=row[12], recorded_at=row[13],
                source=row[14] if row[14] in ("face", "manual") else "manual",
                match_score=row[15],
            )
            for index, row in enumerate(result.all(), start=1)
        ]
        return items, total

    # ------------------------------------------------------------------ #
    # Rekap per kelas
    # ------------------------------------------------------------------ #

    async def class_recap(
        self, class_id: UUID, *, academic_year: str | None = None, semester: str | None = None
    ) -> ClassRecapResponse:
        class_group = await self.session.get(ClassGroup, class_id)
        if class_group is None:
            raise ConsoleNotFoundError("Kelas tidak ditemukan.")

        schedule_statement = (
            select(ClassSchedule, Subject, Lecturer.full_name)
            .join(Subject, Subject.id == ClassSchedule.subject_id)
            .outerjoin(Lecturer, Lecturer.id == ClassSchedule.lecturer_id)
            .where(ClassSchedule.class_id == class_id)
            .order_by(Subject.subject_name.asc())
        )
        if academic_year:
            schedule_statement = schedule_statement.where(ClassSchedule.academic_year == academic_year)
        if semester:
            schedule_statement = schedule_statement.where(ClassSchedule.semester == semester)
        schedule_rows = (await self.session.execute(schedule_statement)).all()

        students = list((await self.session.execute(
            select(Person)
            .where(Person.class_id == class_id, Person.is_deleted.is_(False))
            .order_by(Person.student_id.asc(), Person.full_name.asc())
        )).scalars().all())

        schedule_ids = [schedule.id for schedule, _subject, _name in schedule_rows]

        # One query for every meeting of every subject, then one for every
        # present record across them: the cost no longer grows with the number
        # of subjects the class takes.
        meetings_by_schedule: dict[UUID, list[tuple[UUID, str]]] = {}
        held_meeting_ids: list[UUID] = []
        schedule_of_meeting: dict[UUID, UUID] = {}
        if schedule_ids:
            meeting_rows = await self.session.execute(
                select(ScheduleMeeting.schedule_id, ScheduleMeeting.id, ScheduleMeeting.status)
                .where(ScheduleMeeting.schedule_id.in_(schedule_ids))
            )
            for schedule_id, meeting_id, status in meeting_rows.all():
                meetings_by_schedule.setdefault(schedule_id, []).append((meeting_id, status))
                schedule_of_meeting[meeting_id] = schedule_id
                if status == "held":
                    held_meeting_ids.append(meeting_id)

        present_by_schedule_id: dict[UUID, dict[UUID, int]] = {}
        if held_meeting_ids:
            present_rows = await self.session.execute(
                select(AttendanceRecord.meeting_id, AttendanceRecord.person_id)
                .where(AttendanceRecord.meeting_id.in_(held_meeting_ids), AttendanceRecord.status == "H")
            )
            for meeting_id, person_id in present_rows.all():
                bucket = present_by_schedule_id.setdefault(schedule_of_meeting[meeting_id], {})
                bucket[person_id] = bucket.get(person_id, 0) + 1

        subjects: list[ClassRecapSubject] = []
        present_by_schedule: list[dict[UUID, int]] = []
        held_by_schedule: list[int] = []

        for schedule, subject, lecturer_name in schedule_rows:
            meetings = meetings_by_schedule.get(schedule.id, [])
            held = sum(1 for _id, status in meetings if status == "held")
            held_by_schedule.append(held)
            subjects.append(
                ClassRecapSubject(
                    schedule_id=schedule.id,
                    subject_id=subject.id,
                    subject_code=subject.subject_code,
                    subject_name=subject.subject_name,
                    lecturer_name=lecturer_name,
                    held_meetings=held,
                    total_meetings=len(meetings),
                )
            )
            present_by_schedule.append(present_by_schedule_id.get(schedule.id, {}))

        rows: list[ClassRecapRow] = []
        for index, person in enumerate(students, start=1):
            percents: list[float | None] = []
            for schedule_index, held in enumerate(held_by_schedule):
                if held <= 0:
                    # No meeting held yet: report "no data", not 0%.
                    percents.append(None)
                    continue
                percents.append(attendance_percent(present_by_schedule[schedule_index].get(person.id, 0), held))
            known = [value for value in percents if value is not None]
            rows.append(
                ClassRecapRow(
                    no=index,
                    person_id=person.id,
                    student_id=person.student_id,
                    full_name=person.full_name,
                    percents=percents,
                    average_percent=round(sum(known) / len(known), 2) if known else None,
                )
            )

        class_average = [row.average_percent for row in rows if row.average_percent is not None]
        return ClassRecapResponse(
            class_id=class_group.id,
            class_code=class_group.class_code,
            class_name=class_group.class_name,
            academic_year=academic_year,
            semester=semester,
            subjects=subjects,
            rows=rows,
            student_count=len(rows),
            average_percent=round(sum(class_average) / len(class_average), 2) if class_average else None,
        )

    # ------------------------------------------------------------------ #
    # Enrollment
    # ------------------------------------------------------------------ #

    async def list_enrollments(self, person_id: UUID) -> list[EnrollmentRead]:
        result = await self.session.execute(
            select(StudentEnrollment, ClassGroup.class_code, ClassGroup.class_name)
            .join(ClassGroup, ClassGroup.id == StudentEnrollment.class_id)
            .where(StudentEnrollment.person_id == person_id)
            .order_by(StudentEnrollment.status.asc(), StudentEnrollment.created_at.desc())
        )
        return [self._enrollment_read(row) for row in result.all()]

    async def upsert_enrollment(self, person_id: UUID, request: EnrollmentWrite) -> EnrollmentRead:
        """Move the student to a class, closing whatever enrollment was active.

        Keeping ``Person.class_id`` in step is what lets every existing query —
        attendance sheets, recap, kiosk matching — stay exactly as it was.
        """
        person = await self.session.get(Person, person_id)
        if person is None:
            raise ConsoleNotFoundError("Siswa tidak ditemukan.")
        class_group = await self.session.get(ClassGroup, request.class_id)
        if class_group is None:
            raise ConsoleNotFoundError("Kelas tidak ditemukan.")

        active = (await self.session.execute(
            select(StudentEnrollment).where(
                StudentEnrollment.person_id == person_id, StudentEnrollment.status == "active"
            )
        )).scalar_one_or_none()

        if active is not None and active.class_id == request.class_id:
            active.status = request.status
            active.start_date = request.start_date or active.start_date
            active.note = request.note
            if request.status == "inactive":
                active.end_date = active.end_date or wita_today()
                person.class_id = None
            else:
                active.end_date = None
                person.class_id = request.class_id
            await self.session.flush()
            return (await self.list_enrollments(person_id))[0]

        if active is not None:
            active.status = "inactive"
            active.end_date = wita_today()
            await self.session.flush()

        enrollment = StudentEnrollment(
            person_id=person_id,
            class_id=request.class_id,
            status=request.status,
            start_date=request.start_date or wita_today(),
            note=request.note,
        )
        self.session.add(enrollment)
        person.class_id = request.class_id if request.status == "active" else None
        await self.session.flush()
        LOGGER.info(
            "student_enrollment_changed",
            extra={"person_id": str(person_id), "class_id": str(request.class_id), "enrollment_status": request.status},
        )
        result = await self.session.execute(
            select(StudentEnrollment, ClassGroup.class_code, ClassGroup.class_name)
            .join(ClassGroup, ClassGroup.id == StudentEnrollment.class_id)
            .where(StudentEnrollment.id == enrollment.id)
        )
        return self._enrollment_read(result.one())

    @staticmethod
    def _enrollment_read(row) -> EnrollmentRead:
        enrollment, class_code, class_name = row
        return EnrollmentRead(
            enrollment_id=enrollment.id,
            person_id=enrollment.person_id,
            class_id=enrollment.class_id,
            class_code=class_code,
            class_name=class_name,
            status=enrollment.status,
            start_date=enrollment.start_date,
            end_date=enrollment.end_date,
            note=enrollment.note,
            created_at=enrollment.created_at,
            updated_at=enrollment.updated_at,
        )

    # ------------------------------------------------------------------ #
    # Detail siswa / kelas
    # ------------------------------------------------------------------ #

    async def student_detail(self, person_id: UUID) -> StudentDetailResponse:
        row = (await self.session.execute(
            select(Person, ClassGroup.class_code, ClassGroup.class_name)
            .outerjoin(ClassGroup, ClassGroup.id == Person.class_id)
            .where(Person.id == person_id)
        )).one_or_none()
        if row is None:
            raise ConsoleNotFoundError("Siswa tidak ditemukan.")
        person, class_code, class_name = row

        sample_count = int((await self.session.execute(
            select(func.count()).select_from(
                select(AttendanceLog.id).where(AttendanceLog.person_id == person_id).subquery()
            )
        )).scalar_one())
        last_seen = (await self.session.execute(
            select(func.max(AttendanceLog.created_at)).where(AttendanceLog.person_id == person_id)
        )).scalar_one()

        # Per-subject attendance for whatever class the student is in now.
        summaries: list[StudentSubjectSummary] = []
        if person.class_id is not None:
            schedule_rows = (await self.session.execute(
                select(ClassSchedule, Subject)
                .join(Subject, Subject.id == ClassSchedule.subject_id)
                .where(ClassSchedule.class_id == person.class_id)
                .order_by(Subject.subject_name.asc())
            )).all()
            schedule_ids = [schedule.id for schedule, _subject in schedule_rows]

            # Held meetings for every subject at once, then this student's
            # records across all of them — two queries instead of two per
            # subject.
            held_by_schedule: dict[UUID, list[UUID]] = {}
            schedule_of_meeting: dict[UUID, UUID] = {}
            if schedule_ids:
                held_rows = await self.session.execute(
                    select(ScheduleMeeting.schedule_id, ScheduleMeeting.id).where(
                        ScheduleMeeting.schedule_id.in_(schedule_ids), ScheduleMeeting.status == "held"
                    )
                )
                for schedule_id, meeting_id in held_rows.all():
                    held_by_schedule.setdefault(schedule_id, []).append(meeting_id)
                    schedule_of_meeting[meeting_id] = schedule_id

            counts_by_schedule: dict[UUID, dict[str, int]] = {}
            if schedule_of_meeting:
                status_rows = await self.session.execute(
                    select(AttendanceRecord.meeting_id, AttendanceRecord.status).where(
                        AttendanceRecord.meeting_id.in_(list(schedule_of_meeting)),
                        AttendanceRecord.person_id == person_id,
                    )
                )
                for meeting_id, status_value in status_rows.all():
                    bucket = counts_by_schedule.setdefault(
                        schedule_of_meeting[meeting_id], {"H": 0, "S": 0, "I": 0, "A": 0}
                    )
                    if status_value in bucket:
                        bucket[status_value] += 1

            for schedule, subject in schedule_rows:
                held_ids = held_by_schedule.get(schedule.id, [])
                counts = counts_by_schedule.get(schedule.id, {"H": 0, "S": 0, "I": 0, "A": 0})
                summaries.append(
                    StudentSubjectSummary(
                        subject_id=subject.id,
                        subject_code=subject.subject_code,
                        subject_name=subject.subject_name,
                        hadir=counts["H"], sakit=counts["S"], izin=counts["I"], alpha=counts["A"],
                        held_meetings=len(held_ids),
                        attendance_percent=attendance_percent(counts["H"], len(held_ids)),
                    )
                )

        return StudentDetailResponse(
            person_id=person.id,
            student_id=person.student_id,
            full_name=person.full_name,
            email=person.email,
            address=person.address,
            class_id=person.class_id,
            class_code=class_code,
            class_name=class_name,
            is_active=person.is_active,
            has_face_profile=person.primary_template_id is not None,
            sample_count=sample_count,
            last_seen_at=last_seen,
            enrollments=await self.list_enrollments(person_id),
            subjects=summaries,
        )

    async def class_detail(self, class_id: UUID) -> ClassDetailResponse:
        row = (await self.session.execute(
            select(ClassGroup, Lecturer.full_name)
            .outerjoin(Lecturer, Lecturer.id == ClassGroup.lecturer_id)
            .where(ClassGroup.id == class_id)
        )).one_or_none()
        if row is None:
            raise ConsoleNotFoundError("Kelas tidak ditemukan.")
        class_group, lecturer_name = row

        schedule_count = int((await self.session.execute(
            select(func.count(ClassSchedule.id)).where(ClassSchedule.class_id == class_id)
        )).scalar_one())

        student_rows = (await self.session.execute(
            select(Person, StudentEnrollment.status, StudentEnrollment.start_date)
            .outerjoin(
                StudentEnrollment,
                (StudentEnrollment.person_id == Person.id) & (StudentEnrollment.status == "active"),
            )
            .where(Person.class_id == class_id, Person.is_deleted.is_(False))
            .order_by(Person.student_id.asc(), Person.full_name.asc())
        )).all()

        students = [
            ClassStudentRow(
                no=index,
                person_id=person.id,
                student_id=person.student_id,
                full_name=person.full_name,
                is_active=person.is_active,
                has_face_profile=person.primary_template_id is not None,
                enrollment_status=status if status in ("active", "inactive") else None,
                start_date=start_date,
            )
            for index, (person, status, start_date) in enumerate(student_rows, start=1)
        ]

        return ClassDetailResponse(
            class_id=class_group.id,
            class_code=class_group.class_code,
            class_name=class_group.class_name,
            lecturer_id=class_group.lecturer_id,
            lecturer_name=lecturer_name,
            description=class_group.description,
            is_active=class_group.is_active,
            student_count=len(students),
            schedule_count=schedule_count,
            students=students,
        )

    # ------------------------------------------------------------------ #
    # Pengaturan
    # ------------------------------------------------------------------ #

    async def get_settings(self) -> SettingsResponse:
        rows = (await self.session.execute(
            select(AppSetting).where(AppSetting.key.in_(SETTING_KEYS))
        )).scalars().all()
        values = {row.key: row.value for row in rows}
        updated = max((row.updated_at for row in rows), default=None)
        return SettingsResponse(**values, updated_at=updated)

    async def save_settings(self, payload: SettingsPayload) -> SettingsResponse:
        incoming = payload.model_dump()
        for key in SETTING_KEYS:
            value = incoming.get(key)
            setting = await self.session.get(AppSetting, key)
            if setting is None:
                self.session.add(AppSetting(key=key, value=value))
            else:
                setting.value = value
        await self.session.flush()
        return await self.get_settings()
