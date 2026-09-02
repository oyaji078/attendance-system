"""Service-level rules for jadwal, pertemuan, and manual attendance.

Uses a lightweight in-memory fake repository rather than a live database, in
line with the other unit tests in this suite.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from db.repositories.academic import MeetingProjection, ScheduleProjection
from db.schemas.academic_attendance import AttendanceEntry, MeetingWrite
from services.academic.service import (
    AcademicNotFoundError,
    AcademicPermissionError,
    AcademicService,
)

NOW = datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc)


def make_schedule(schedule_id: UUID, class_id: UUID, lecturer_id: UUID | None, total_meetings: int = 12):
    return SimpleNamespace(
        id=schedule_id,
        schedule_code="JDW-0001",
        class_id=class_id,
        subject_id=uuid4(),
        lecturer_id=lecturer_id,
        academic_year="2025/2026",
        semester="ganjil",
        day_of_week="monday",
        start_time=None,
        end_time=None,
        total_meetings=total_meetings,
        room=None,
        is_active=True,
        attendance_session_id=None,
        created_at=NOW,
        updated_at=NOW,
    )


def make_meeting(meeting_id: UUID, schedule_id: UUID, number: int, status: str = "planned"):
    return SimpleNamespace(
        id=meeting_id,
        schedule_id=schedule_id,
        meeting_number=number,
        meeting_date=None,
        topic=None,
        status=status,
        attendance_session_id=None,
        notes=None,
        created_at=NOW,
        updated_at=NOW,
    )


def make_person(person_id: UUID, student_id: str, name: str):
    return SimpleNamespace(id=person_id, student_id=student_id, full_name=name, address="Jl. Mawar 1")


class FakeRecord:
    def __init__(self, meeting_id, person_id, status, note=None, source="manual", recorded_by_admin_id=None):
        self.meeting_id = meeting_id
        self.person_id = person_id
        self.status = status
        self.note = note
        self.source = source
        self.recorded_by_admin_id = recorded_by_admin_id
        self.updated_at = NOW


class FakeAcademicRepository:
    """Mirrors the parts of AcademicRepository the service actually calls."""

    def __init__(self, schedule, students, meetings):
        self.schedule = schedule
        self.students = students
        self.meetings = {meeting.id: meeting for meeting in meetings}
        self.records: list[FakeRecord] = []
        self.flush_calls = 0

    async def get_schedule_projection(self, schedule_id):
        if schedule_id != self.schedule.id:
            return None
        held = sum(1 for m in self.meetings.values() if m.status == "held")
        return ScheduleProjection(
            schedule=self.schedule,
            class_code="XII-RPL-1",
            class_name="XII RPL 1",
            subject_code="PWEB-01",
            subject_name="Pemrograman Web",
            lecturer_name="Budi Santoso",
            student_count=len(self.students),
            meeting_count=len(self.meetings),
            held_meeting_count=held,
        )

    async def get_schedule(self, schedule_id):
        return self.schedule if schedule_id == self.schedule.id else None

    async def list_schedules(self, **filters):
        lecturer_id = filters.get("lecturer_id")
        if lecturer_id is not None and self.schedule.lecturer_id != lecturer_id:
            return []
        return [await self.get_schedule_projection(self.schedule.id)]

    async def list_meetings(self, schedule_id):
        items = sorted(
            (m for m in self.meetings.values() if m.schedule_id == schedule_id),
            key=lambda m: m.meeting_number,
        )
        return [self._meeting_projection(m) for m in items]

    async def get_meeting(self, meeting_id):
        return self.meetings.get(meeting_id)

    async def get_meeting_projection(self, meeting_id):
        meeting = self.meetings.get(meeting_id)
        return None if meeting is None else self._meeting_projection(meeting)

    def _meeting_projection(self, meeting):
        recorded = [r for r in self.records if r.meeting_id == meeting.id]
        return MeetingProjection(
            meeting=meeting,
            recorded_count=len(recorded),
            present_count=sum(1 for r in recorded if r.status == "H"),
        )

    async def existing_meeting_numbers(self, schedule_id):
        return {m.meeting_number for m in self.meetings.values() if m.schedule_id == schedule_id}

    async def add_meetings(self, schedule_id, numbers):
        created = []
        for number in numbers:
            meeting = make_meeting(uuid4(), schedule_id, number)
            self.meetings[meeting.id] = meeting
            created.append(meeting)
        return created

    async def list_class_students(self, class_id):
        return [s for s in self.students] if class_id == self.schedule.class_id else []

    async def list_records_for_meeting(self, meeting_id):
        return [r for r in self.records if r.meeting_id == meeting_id]

    async def list_records_for_meetings(self, meeting_ids):
        return [r for r in self.records if r.meeting_id in set(meeting_ids)]

    async def upsert_records(self, *, meeting_id, entries, recorded_by_admin_id, source="manual"):
        existing = {r.person_id: r for r in self.records if r.meeting_id == meeting_id}
        created = updated = 0
        for person_id, (status, note) in entries.items():
            record = existing.get(person_id)
            if record is None:
                self.records.append(FakeRecord(meeting_id, person_id, status, note, source, recorded_by_admin_id))
                created += 1
            elif record.status != status or record.note != note:
                record.status = status
                record.note = note
                updated += 1
        self.flush_calls += 1
        return created, updated


@pytest.fixture
def setup():
    schedule_id, class_id, lecturer_id = uuid4(), uuid4(), uuid4()
    schedule = make_schedule(schedule_id, class_id, lecturer_id)
    students = [
        make_person(uuid4(), "001", "Ahmad"),
        make_person(uuid4(), "002", "Budi"),
        make_person(uuid4(), "003", "Citra"),
    ]
    meetings = [make_meeting(uuid4(), schedule_id, n) for n in (1, 2)]
    repo = FakeAcademicRepository(schedule, students, meetings)
    return SimpleNamespace(
        repo=repo,
        service=AcademicService(repo),
        schedule_id=schedule_id,
        lecturer_id=lecturer_id,
        students=students,
        meetings=meetings,
    )


async def test_sheet_lists_every_student_of_the_class(setup):
    sheet = await setup.service.attendance_sheet(setup.meetings[0].id)
    assert sheet.student_count == 3
    assert [s.full_name for s in sheet.students] == ["Ahmad", "Budi", "Citra"]
    assert [s.no for s in sheet.students] == [1, 2, 3]
    # Nothing saved yet: every status is blank rather than defaulted.
    assert all(s.status is None for s in sheet.students)


async def test_save_then_reopen_shows_saved_status(setup):
    meeting = setup.meetings[0]
    entries = [
        AttendanceEntry(person_id=setup.students[0].id, status="H"),
        AttendanceEntry(person_id=setup.students[1].id, status="S"),
        AttendanceEntry(person_id=setup.students[2].id, status="I"),
    ]
    created, updated, skipped = await setup.service.save_attendance(meeting.id, entries)
    assert (created, updated, skipped) == (3, 0, 0)

    sheet = await setup.service.attendance_sheet(meeting.id)
    assert [s.status for s in sheet.students] == ["H", "S", "I"]


async def test_resaving_updates_in_place_without_duplicating(setup):
    meeting = setup.meetings[0]
    person = setup.students[0].id
    await setup.service.save_attendance(meeting.id, [AttendanceEntry(person_id=person, status="A")])
    created, updated, _ = await setup.service.save_attendance(
        meeting.id, [AttendanceEntry(person_id=person, status="H")]
    )
    assert (created, updated) == (0, 1)
    rows = [r for r in setup.repo.records if r.meeting_id == meeting.id and r.person_id == person]
    assert len(rows) == 1
    assert rows[0].status == "H"


async def test_meeting_two_does_not_overwrite_meeting_one(setup):
    first, second = setup.meetings
    person = setup.students[0].id
    await setup.service.save_attendance(first.id, [AttendanceEntry(person_id=person, status="H")])
    await setup.service.save_attendance(second.id, [AttendanceEntry(person_id=person, status="A")])

    sheet_one = await setup.service.attendance_sheet(first.id)
    sheet_two = await setup.service.attendance_sheet(second.id)
    assert sheet_one.students[0].status == "H"
    assert sheet_two.students[0].status == "A"
    assert len(setup.repo.records) == 2


async def test_saving_marks_the_meeting_as_held(setup):
    meeting = setup.meetings[0]
    assert meeting.status == "planned"
    await setup.service.save_attendance(meeting.id, [AttendanceEntry(person_id=setup.students[0].id, status="H")])
    assert meeting.status == "held"


async def test_entries_for_other_classes_are_skipped_not_written(setup):
    outsider = uuid4()
    created, updated, skipped = await setup.service.save_attendance(
        setup.meetings[0].id,
        [
            AttendanceEntry(person_id=setup.students[0].id, status="H"),
            AttendanceEntry(person_id=outsider, status="H"),
        ],
    )
    assert (created, updated, skipped) == (1, 0, 1)
    assert all(r.person_id != outsider for r in setup.repo.records)


async def test_generate_creates_meetings_one_to_twelve(setup):
    schedule, meetings = await setup.service.generate_meetings(setup.schedule_id)
    assert [m.meeting_number for m in meetings] == list(range(1, 13))
    assert schedule.meeting_count == 12


async def test_generate_is_idempotent_and_keeps_existing_meetings(setup):
    await setup.service.save_attendance(setup.meetings[0].id, [AttendanceEntry(person_id=setup.students[0].id, status="H")])
    first_id = setup.meetings[0].id
    await setup.service.generate_meetings(setup.schedule_id)
    _, meetings = await setup.service.generate_meetings(setup.schedule_id)
    assert len(meetings) == 12
    # Meeting 1 was reused, so its saved attendance survives.
    assert any(m.meeting_id == first_id for m in meetings)
    assert len([r for r in setup.repo.records if r.meeting_id == first_id]) == 1


async def test_meeting_count_is_not_hardcoded_to_twelve(setup):
    _, meetings = await setup.service.generate_meetings(setup.schedule_id, total_meetings=16)
    assert [m.meeting_number for m in meetings] == list(range(1, 17))
    assert setup.repo.schedule.total_meetings == 16


async def test_recap_counts_and_percentage(setup):
    first, second = setup.meetings
    ahmad, budi, citra = (s.id for s in setup.students)
    await setup.service.save_attendance(
        first.id,
        [
            AttendanceEntry(person_id=ahmad, status="H"),
            AttendanceEntry(person_id=budi, status="S"),
            AttendanceEntry(person_id=citra, status="A"),
        ],
    )
    await setup.service.save_attendance(
        second.id,
        [
            AttendanceEntry(person_id=ahmad, status="H"),
            AttendanceEntry(person_id=budi, status="H"),
            AttendanceEntry(person_id=citra, status="I"),
        ],
    )

    recap = await setup.service.recap(setup.schedule_id)
    assert recap.held_meetings == 2
    by_name = {row.full_name: row for row in recap.rows}
    assert by_name["Ahmad"].hadir == 2 and by_name["Ahmad"].attendance_percent == 100.0
    assert by_name["Budi"].hadir == 1 and by_name["Budi"].sakit == 1 and by_name["Budi"].attendance_percent == 50.0
    assert by_name["Citra"].hadir == 0 and by_name["Citra"].izin == 1 and by_name["Citra"].alpha == 1
    assert by_name["Citra"].attendance_percent == 0.0
    assert recap.average_percent == 50.0


async def test_recap_ignores_meetings_not_yet_held(setup):
    # 12 meetings planned, only meeting 1 held with everyone present.
    await setup.service.generate_meetings(setup.schedule_id)
    first = next(m for m in setup.repo.meetings.values() if m.meeting_number == 1)
    await setup.service.save_attendance(
        first.id, [AttendanceEntry(person_id=s.id, status="H") for s in setup.students]
    )
    recap = await setup.service.recap(setup.schedule_id)
    assert recap.total_meetings == 12
    assert recap.held_meetings == 1
    # 100%, not 1/12 — the 11 future meetings are not absences.
    assert all(row.attendance_percent == 100.0 for row in recap.rows)
    assert all(row.alpha == 0 for row in recap.rows)


async def test_lecturer_scope_allows_owner(setup):
    sheet = await setup.service.attendance_sheet(setup.meetings[0].id, lecturer_scope=setup.lecturer_id)
    assert sheet.student_count == 3


async def test_lecturer_scope_blocks_other_lecturers(setup):
    stranger = uuid4()
    with pytest.raises(AcademicPermissionError):
        await setup.service.attendance_sheet(setup.meetings[0].id, lecturer_scope=stranger)
    with pytest.raises(AcademicPermissionError):
        await setup.service.recap(setup.schedule_id, lecturer_scope=stranger)
    with pytest.raises(AcademicPermissionError):
        await setup.service.save_attendance(
            setup.meetings[0].id,
            [AttendanceEntry(person_id=setup.students[0].id, status="H")],
            lecturer_scope=stranger,
        )
    # The blocked save wrote nothing.
    assert setup.repo.records == []


async def test_lecturer_cannot_widen_scope_through_the_filter(setup):
    stranger = uuid4()
    # Asking for another lecturer's schedules while scoped returns only own.
    items = await setup.service.list_schedules(lecturer_id=stranger, lecturer_scope=setup.lecturer_id)
    assert all(item.lecturer_id == setup.lecturer_id for item in items)


async def test_unknown_meeting_raises_not_found(setup):
    with pytest.raises(AcademicNotFoundError):
        await setup.service.attendance_sheet(uuid4())


async def test_update_meeting_sets_date_and_status(setup):
    meeting = setup.meetings[0]
    payload = MeetingWrite(meeting_date=date(2026, 8, 24), topic="Pengenalan HTML", status="held")
    result = await setup.service.update_meeting(meeting.id, payload)
    assert result.meeting_date == date(2026, 8, 24)
    assert result.topic == "Pengenalan HTML"
    assert result.status == "held"
