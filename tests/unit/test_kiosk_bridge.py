"""The kiosk -> recap bridge.

A face scan has to become a Hadir on a pertemuan, otherwise the recap only ever
shows manually entered attendance. These pin which meeting a scan lands on, when
a jadwal can be inferred at all, and when an existing status must be left alone.

The fake session dispatches on the entity being queried rather than on call
order, so adding a query to the bridge does not invalidate every test here.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from db.models.entities import AttendanceRecord, AttendanceSession, ClassSchedule, ScheduleMeeting
from services.academic.kiosk_bridge import (
    record_face_attendance,
    resolve_meeting_for_session,
    resolve_schedule_for_session,
)

WITA = timezone(timedelta(hours=8))
TODAY = date(2026, 8, 24)          # a Monday
MONDAY_10AM = datetime(2026, 8, 24, 10, 0, tzinfo=WITA)
SESSION_ID = uuid4()
CLASS_ID = uuid4()
PERSON_ID = uuid4()


def make_schedule(**kwargs):
    defaults = {
        "id": uuid4(),
        "class_id": CLASS_ID,
        "attendance_session_id": None,
        "total_meetings": 4,
        "is_active": True,
        "day_of_week": None,
        "start_time": None,
        "end_time": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_meeting(schedule_id, number, *, status="planned", meeting_date=None):
    return SimpleNamespace(
        id=uuid4(), schedule_id=schedule_id, meeting_number=number,
        status=status, meeting_date=meeting_date,
    )


class FakeResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        rows = self._rows
        return SimpleNamespace(all=lambda: rows, first=lambda: (rows[0] if rows else None))


class FakeSession:
    def __init__(self, *, schedules=(), meetings=(), records=(), kiosk_session=None):
        self.schedules = list(schedules)
        self.meetings = list(meetings)
        self.records = list(records)
        self.kiosk_session = kiosk_session
        self.added = []

    async def get(self, model, key):
        if model is AttendanceSession:
            return self.kiosk_session
        return None

    async def flush(self):
        return None

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        for obj in objs:
            self.added.append(obj)

    async def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        text = str(statement)

        if entity is ClassSchedule:
            if "attendance_session_id" in text and "class_id" not in text.split("WHERE")[-1]:
                return FakeResult([s for s in self.schedules if s.attendance_session_id == SESSION_ID])
            return FakeResult([s for s in self.schedules if s.class_id == CLASS_ID and s.is_active])

        if entity is ScheduleMeeting:
            rows = self.meetings
            where = text.split("WHERE")[-1]
            if "meeting_date" in where:
                # Read the date actually bound to the query, so replaying several
                # days does not keep matching the first one.
                params = statement.compile().params
                wanted = next((v for k, v in params.items() if "meeting_date" in k), None)
                rows = [m for m in rows if m.meeting_date == wanted]
            elif "status" in where:
                rows = [m for m in rows if m.status == "planned"]
            return FakeResult(sorted(rows, key=lambda m: m.meeting_number))

        if entity is AttendanceRecord:
            return FakeResult(self.records)

        return FakeResult([])


# --------------------------------------------------------------------------- #
# Which jadwal a scan belongs to
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_the_jadwal_that_owns_the_session_wins():
    owned = make_schedule(attendance_session_id=SESSION_ID)
    other = make_schedule()
    session = FakeSession(schedules=[owned, other])
    assert await resolve_schedule_for_session(session, SESSION_ID) is owned


@pytest.mark.asyncio
async def test_an_unlinked_session_falls_back_to_the_only_jadwal_of_its_class():
    # Sessions created before jadwal existed still have to reach the recap.
    only = make_schedule()
    session = FakeSession(
        schedules=[only],
        kiosk_session=SimpleNamespace(id=SESSION_ID, class_id=CLASS_ID),
    )
    assert await resolve_schedule_for_session(session, SESSION_ID) is only


@pytest.mark.asyncio
async def test_several_subjects_resolve_to_the_lesson_running_now():
    morning = make_schedule(day_of_week="monday", start_time=time(7, 0), end_time=time(8, 30))
    now = make_schedule(day_of_week="monday", start_time=time(9, 30), end_time=time(11, 0))
    session = FakeSession(
        schedules=[morning, now],
        kiosk_session=SimpleNamespace(id=SESSION_ID, class_id=CLASS_ID),
    )
    assert await resolve_schedule_for_session(session, SESSION_ID, now=MONDAY_10AM) is now


@pytest.mark.asyncio
async def test_ambiguous_class_records_nothing_rather_than_guessing():
    # Filing attendance against the wrong subject is worse than filing none.
    a = make_schedule(day_of_week="monday", start_time=time(9, 0), end_time=time(11, 0))
    b = make_schedule(day_of_week="monday", start_time=time(9, 0), end_time=time(11, 0))
    session = FakeSession(
        schedules=[a, b],
        kiosk_session=SimpleNamespace(id=SESSION_ID, class_id=CLASS_ID),
    )
    assert await resolve_schedule_for_session(session, SESSION_ID, now=MONDAY_10AM) is None


@pytest.mark.asyncio
async def test_session_without_a_class_cannot_be_resolved():
    session = FakeSession(kiosk_session=SimpleNamespace(id=SESSION_ID, class_id=None))
    assert await resolve_schedule_for_session(session, SESSION_ID) is None


# --------------------------------------------------------------------------- #
# Which pertemuan the scan lands on
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_meeting_already_dated_today_is_reused():
    schedule = make_schedule(attendance_session_id=SESSION_ID)
    today_meeting = make_meeting(schedule.id, 3, status="held", meeting_date=TODAY)
    session = FakeSession(schedules=[schedule], meetings=[today_meeting])
    resolved = await resolve_meeting_for_session(session, SESSION_ID, on_date=TODAY)
    assert resolved is today_meeting


@pytest.mark.asyncio
async def test_first_scan_claims_the_earliest_planned_meeting():
    schedule = make_schedule(attendance_session_id=SESSION_ID)
    planned = [make_meeting(schedule.id, n) for n in (1, 2, 3)]
    session = FakeSession(schedules=[schedule], meetings=planned)
    resolved = await resolve_meeting_for_session(session, SESSION_ID, on_date=TODAY)
    assert resolved.meeting_number == 1
    # Dated and held is what makes it count in the attendance denominator.
    assert resolved.meeting_date == TODAY
    assert resolved.status == "held"


@pytest.mark.asyncio
async def test_a_jadwal_with_no_meetings_gets_them_created():
    # This was the live symptom: a schedule with zero meetings silently swallowed
    # every scan, so the recap never showed a percentage.
    schedule = make_schedule(attendance_session_id=SESSION_ID, total_meetings=4)
    session = FakeSession(schedules=[schedule], meetings=[])
    await resolve_meeting_for_session(session, SESSION_ID, on_date=TODAY)
    assert len(session.added) == 4
    assert [m.meeting_number for m in session.added] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_a_finished_term_records_nothing():
    schedule = make_schedule(attendance_session_id=SESSION_ID)
    done = [make_meeting(schedule.id, n, status="held", meeting_date=date(2026, 1, n)) for n in (1, 2)]
    session = FakeSession(schedules=[schedule], meetings=done)
    assert await resolve_meeting_for_session(session, SESSION_ID, on_date=TODAY) is None


# --------------------------------------------------------------------------- #
# What gets written
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_scan_creates_a_hadir_record():
    schedule = make_schedule(attendance_session_id=SESSION_ID)
    session = FakeSession(schedules=[schedule], meetings=[make_meeting(schedule.id, 1)])
    await record_face_attendance(session, attendance_session_id=SESSION_ID, person_id=PERSON_ID, on_date=TODAY)
    written = [o for o in session.added if getattr(o, "status", None) == "H"]
    assert len(written) == 1
    assert written[0].source == "face"


@pytest.mark.asyncio
async def test_a_teachers_manual_status_is_never_overwritten_by_the_camera():
    schedule = make_schedule(attendance_session_id=SESSION_ID)
    existing = SimpleNamespace(status="S", source="manual")
    session = FakeSession(
        schedules=[schedule], meetings=[make_meeting(schedule.id, 1)], records=[existing]
    )
    await record_face_attendance(session, attendance_session_id=SESSION_ID, person_id=PERSON_ID, on_date=TODAY)
    assert existing.status == "S"
    assert existing.source == "manual"
    assert not [o for o in session.added if getattr(o, "status", None) == "H"]


@pytest.mark.asyncio
async def test_rescanning_does_not_duplicate_the_record():
    schedule = make_schedule(attendance_session_id=SESSION_ID)
    existing = SimpleNamespace(status="H", source="face")
    session = FakeSession(
        schedules=[schedule], meetings=[make_meeting(schedule.id, 1)], records=[existing]
    )
    await record_face_attendance(session, attendance_session_id=SESSION_ID, person_id=PERSON_ID, on_date=TODAY)
    assert not [o for o in session.added if getattr(o, "status", None) == "H"]
    assert existing.status == "H"


@pytest.mark.asyncio
async def test_the_match_score_is_kept_on_the_record():
    # The console shows this number as "Akurasi"; it has to be the score of the
    # scan that filed the row, not one recomputed later.
    schedule = make_schedule(attendance_session_id=SESSION_ID)
    session = FakeSession(schedules=[schedule], meetings=[make_meeting(schedule.id, 1)])
    await record_face_attendance(
        session, attendance_session_id=SESSION_ID, person_id=PERSON_ID, on_date=TODAY, confidence=0.83
    )
    written = [o for o in session.added if getattr(o, "status", None) == "H"]
    assert written[0].match_score == 0.83


@pytest.mark.asyncio
async def test_rescanning_keeps_the_best_match_of_the_lesson():
    # Several scans describe one Hadir, so the row reports the strongest
    # evidence for it rather than whichever frame came last.
    schedule = make_schedule(attendance_session_id=SESSION_ID)
    existing = SimpleNamespace(status="H", source="face", match_score=0.62)
    session = FakeSession(
        schedules=[schedule], meetings=[make_meeting(schedule.id, 1)], records=[existing]
    )
    await record_face_attendance(
        session, attendance_session_id=SESSION_ID, person_id=PERSON_ID, on_date=TODAY, confidence=0.91
    )
    assert existing.match_score == 0.91
    await record_face_attendance(
        session, attendance_session_id=SESSION_ID, person_id=PERSON_ID, on_date=TODAY, confidence=0.55
    )
    assert existing.match_score == 0.91


@pytest.mark.asyncio
async def test_unresolvable_session_writes_nothing():
    session = FakeSession(kiosk_session=SimpleNamespace(id=SESSION_ID, class_id=None))
    assert await record_face_attendance(
        session, attendance_session_id=SESSION_ID, person_id=PERSON_ID, on_date=TODAY
    ) is None
    assert session.added == []


# --------------------------------------------------------------------------- #
# Backfilling scans that never reached the recap
# --------------------------------------------------------------------------- #


class BackfillSession(FakeSession):
    """Adds the attendance_logs query the backfill walks."""

    def __init__(self, *, logs=(), **kwargs):
        super().__init__(**kwargs)
        self.logs = list(logs)

    async def execute(self, statement):
        from db.models.entities import AttendanceLog

        if statement.column_descriptions[0]["entity"] is AttendanceLog:
            return FakeResult([])  # rows are read via .all(), stubbed below
        return await super().execute(statement)


@pytest.mark.asyncio
async def test_backfill_groups_a_day_into_one_meeting(monkeypatch):
    from services.academic import kiosk_bridge

    schedule = make_schedule(attendance_session_id=SESSION_ID)
    meetings = [make_meeting(schedule.id, n) for n in (1, 2, 3)]
    session = FakeSession(schedules=[schedule], meetings=meetings)

    day = date(2026, 8, 25)
    people = [uuid4(), uuid4()]
    rows = [
        (SESSION_ID, people[0], datetime(2026, 8, 25, 6, 52, tzinfo=timezone.utc), 0.81),
        (SESSION_ID, people[1], datetime(2026, 8, 25, 6, 59, tzinfo=timezone.utc), 0.64),
    ]

    async def fake_execute(statement):
        from db.models.entities import AttendanceLog

        if statement.column_descriptions[0]["entity"] is AttendanceLog:
            return SimpleNamespace(all=lambda: rows)
        return await FakeSession.execute(session, statement)

    monkeypatch.setattr(session, "execute", fake_execute)

    result = await kiosk_bridge.backfill_from_logs(session)
    # Two students scanned on the same day: one pertemuan, two Hadir.
    assert result["days"] == 1
    assert result["recorded"] == 2
    assert [o.match_score for o in session.added if getattr(o, "status", None) == "H"] == [0.81, 0.64]
    assert meetings[0].meeting_date == day
    assert meetings[0].status == "held"
    assert meetings[1].meeting_date is None


@pytest.mark.asyncio
async def test_backfill_gives_each_day_its_own_meeting(monkeypatch):
    from services.academic import kiosk_bridge

    schedule = make_schedule(attendance_session_id=SESSION_ID)
    meetings = [make_meeting(schedule.id, n) for n in (1, 2, 3)]
    session = FakeSession(schedules=[schedule], meetings=meetings)

    person = uuid4()
    rows = [
        (SESSION_ID, person, datetime(2026, 8, 24, 2, 0, tzinfo=timezone.utc), 0.72),
        (SESSION_ID, person, datetime(2026, 8, 25, 2, 0, tzinfo=timezone.utc), 0.69),
    ]

    async def fake_execute(statement):
        from db.models.entities import AttendanceLog

        if statement.column_descriptions[0]["entity"] is AttendanceLog:
            return SimpleNamespace(all=lambda: rows)
        return await FakeSession.execute(session, statement)

    monkeypatch.setattr(session, "execute", fake_execute)

    result = await kiosk_bridge.backfill_from_logs(session)
    assert result["days"] == 2
    # Two teaching days must not both land on pertemuan 1.
    assert meetings[0].status == "held"
    assert meetings[1].status == "held"
    assert meetings[0].meeting_date < meetings[1].meeting_date


@pytest.mark.asyncio
async def test_backfill_fills_a_missing_score_without_touching_the_status(monkeypatch):
    from services.academic import kiosk_bridge

    schedule = make_schedule(attendance_session_id=SESSION_ID)
    meetings = [make_meeting(schedule.id, 1)]
    # Filed by an earlier version that had nowhere to put the score, and a row
    # a teacher has since corrected by hand.
    unscored = SimpleNamespace(status="H", source="face", match_score=None)
    session = FakeSession(schedules=[schedule], meetings=meetings, records=[unscored])

    rows = [(SESSION_ID, PERSON_ID, datetime(2026, 8, 25, 2, 0, tzinfo=timezone.utc), 0.77)]

    async def fake_execute(statement):
        from db.models.entities import AttendanceLog

        if statement.column_descriptions[0]["entity"] is AttendanceLog:
            return SimpleNamespace(all=lambda: rows)
        return await FakeSession.execute(session, statement)

    monkeypatch.setattr(session, "execute", fake_execute)

    result = await kiosk_bridge.backfill_from_logs(session)
    assert result["recorded"] == 0
    assert result["scored"] == 1
    assert unscored.match_score == 0.77
    assert unscored.status == "H"


@pytest.mark.asyncio
async def test_backfill_leaves_a_corrected_row_alone(monkeypatch):
    from services.academic import kiosk_bridge

    schedule = make_schedule(attendance_session_id=SESSION_ID)
    corrected = SimpleNamespace(status="S", source="manual", match_score=None)
    session = FakeSession(
        schedules=[schedule], meetings=[make_meeting(schedule.id, 1)], records=[corrected]
    )

    rows = [(SESSION_ID, PERSON_ID, datetime(2026, 8, 25, 2, 0, tzinfo=timezone.utc), 0.77)]

    async def fake_execute(statement):
        from db.models.entities import AttendanceLog

        if statement.column_descriptions[0]["entity"] is AttendanceLog:
            return SimpleNamespace(all=lambda: rows)
        return await FakeSession.execute(session, statement)

    monkeypatch.setattr(session, "execute", fake_execute)

    result = await kiosk_bridge.backfill_from_logs(session)
    # A hand-entered status has no face behind it; scoring it would dress a
    # human decision up as a camera one.
    assert result["scored"] == 0
    assert corrected.match_score is None
    assert corrected.status == "S"


@pytest.mark.asyncio
async def test_backfill_counts_days_it_cannot_attribute(monkeypatch):
    from services.academic import kiosk_bridge

    # A session whose class has no jadwal cannot be filed anywhere; the caller
    # reports that instead of guessing.
    session = FakeSession(kiosk_session=SimpleNamespace(id=SESSION_ID, class_id=None))
    rows = [(SESSION_ID, uuid4(), datetime(2026, 8, 25, 2, 0, tzinfo=timezone.utc), 0.7)]

    async def fake_execute(statement):
        from db.models.entities import AttendanceLog

        if statement.column_descriptions[0]["entity"] is AttendanceLog:
            return SimpleNamespace(all=lambda: rows)
        return await FakeSession.execute(session, statement)

    monkeypatch.setattr(session, "execute", fake_execute)

    result = await kiosk_bridge.backfill_from_logs(session)
    assert result["recorded"] == 0
    assert result["skipped_days"] == 1
