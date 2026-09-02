"""The link between a kiosk scan and the academic recap.

``attendance_logs`` is the face-recognition audit trail; ``attendance_records``
is the H/S/I/A register the recap reads. Without this bridge a scan proved a
student was seen but never became a Hadir on any pertemuan, so the recap only
ever reflected manual entry.

Resolving a scan to a pertemuan happens in three steps, each a fallback for the
one before:

1. the jadwal that owns the kiosk session — the direct, unambiguous link;
2. otherwise the class's own jadwal, for sessions made before schedules existed
   (only when exactly one candidate fits, so attendance is never filed against
   the wrong subject);
3. within that jadwal, today's meeting, or the earliest planned one, creating
   the meeting list on demand when the jadwal has none yet.

The bridge is best-effort throughout: a scan must still be recorded in the audit
log even when none of this resolves, so it logs and returns instead of raising.
"""

from __future__ import annotations

from datetime import date as date_type, datetime, time, timedelta, timezone
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import (
    AttendanceRecord,
    AttendanceSession,
    ClassSchedule,
    ScheduleMeeting,
)

LOGGER = logging.getLogger(__name__)

WITA_TZ = timezone(timedelta(hours=8))

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# Meetings created on demand when a jadwal has none. The schedule's own
# total_meetings wins; this only covers a row that somehow has none set.
DEFAULT_TOTAL_MEETINGS = 16


def wita_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(WITA_TZ)


def wita_today() -> date_type:
    return wita_now().date()


def _covers_now(schedule: ClassSchedule, now: datetime) -> bool:
    """Whether this jadwal is the lesson running right now (WITA)."""
    if schedule.day_of_week and schedule.day_of_week != WEEKDAYS[now.weekday()]:
        return False
    if schedule.start_time and schedule.end_time:
        current: time = now.time()
        return schedule.start_time <= current <= schedule.end_time
    # No day/time set means the jadwal is not time-bound, so it always applies.
    return True


async def resolve_schedule_for_session(
    session: AsyncSession, attendance_session_id: UUID, *, now: datetime | None = None
) -> ClassSchedule | None:
    """The jadwal a scan on this session belongs to."""
    owned = (await session.execute(
        select(ClassSchedule).where(ClassSchedule.attendance_session_id == attendance_session_id)
    )).scalar_one_or_none()
    if owned is not None:
        return owned

    # Session made before jadwal existed (or left behind by a deleted one).
    # Fall back to the class it belongs to.
    kiosk_session = await session.get(AttendanceSession, attendance_session_id)
    if kiosk_session is None or kiosk_session.class_id is None:
        return None

    candidates = list((await session.execute(
        select(ClassSchedule).where(
            ClassSchedule.class_id == kiosk_session.class_id,
            ClassSchedule.is_active.is_(True),
        )
    )).scalars().all())
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # Several subjects share the class, so only the lesson happening right now
    # can claim the scan. Anything less certain would file attendance against
    # the wrong subject, which is worse than filing none.
    moment = now or wita_now()
    running = [item for item in candidates if _covers_now(item, moment)]
    if len(running) == 1:
        return running[0]
    LOGGER.info(
        "face_attendance_schedule_ambiguous",
        extra={
            "attendance_session_id": str(attendance_session_id),
            "candidates": len(candidates),
            "running_now": len(running),
        },
    )
    return None


async def ensure_meetings(session: AsyncSession, schedule: ClassSchedule) -> None:
    """Create pertemuan 1..N for a jadwal that has none.

    Without this the first scan of a brand-new jadwal has nowhere to land and
    the recap silently stays empty — the exact symptom of "tidak muncul persen".
    """
    existing = int((await session.execute(
        select(ScheduleMeeting.id).where(ScheduleMeeting.schedule_id == schedule.id).limit(1)
    )).scalar() is not None)
    if existing:
        return
    total = schedule.total_meetings or DEFAULT_TOTAL_MEETINGS
    session.add_all(
        ScheduleMeeting(schedule_id=schedule.id, meeting_number=number, status="planned")
        for number in range(1, total + 1)
    )
    await session.flush()
    LOGGER.info(
        "schedule_meetings_autocreated",
        extra={"schedule_id": str(schedule.id), "total": total},
    )


async def resolve_meeting_for_session(
    session: AsyncSession, attendance_session_id: UUID, *, on_date: date_type | None = None
) -> ScheduleMeeting | None:
    """The pertemuan a scan on this session belongs to.

    1. the meeting already dated today — a second scan in the same lesson,
    2. otherwise the earliest still-planned meeting, which becomes today's.

    Returns ``None`` only when no jadwal can be resolved at all.
    """
    today = on_date or wita_today()

    schedule = await resolve_schedule_for_session(session, attendance_session_id)
    if schedule is None:
        return None

    await ensure_meetings(session, schedule)

    dated = (await session.execute(
        select(ScheduleMeeting)
        .where(ScheduleMeeting.schedule_id == schedule.id, ScheduleMeeting.meeting_date == today)
        .order_by(ScheduleMeeting.meeting_number.asc())
    )).scalars().first()
    if dated is not None:
        return dated

    planned = (await session.execute(
        select(ScheduleMeeting)
        .where(ScheduleMeeting.schedule_id == schedule.id, ScheduleMeeting.status == "planned")
        .order_by(ScheduleMeeting.meeting_number.asc())
    )).scalars().first()
    if planned is None:
        # Every meeting is already held or cancelled — the term is over, so
        # there is nothing left for this scan to count towards.
        LOGGER.info(
            "face_attendance_no_planned_meeting_left",
            extra={"schedule_id": str(schedule.id)},
        )
        return None

    # First scan of the lesson: this planned meeting is the one happening now.
    planned.meeting_date = today
    planned.status = "held"
    return planned


async def record_face_attendance(
    session: AsyncSession,
    *,
    attendance_session_id: UUID,
    person_id: UUID,
    on_date: date_type | None = None,
    confidence: float | None = None,
) -> ScheduleMeeting | None:
    """Mark the student Hadir on the meeting this scan belongs to.

    An existing record is never overwritten: a teacher who already set Sakit or
    Izin for that student keeps their correction, and the camera cannot undo it.

    ``confidence`` is the match score of the scan (0..1). It is copied onto the
    record so the Absensi page can show how sure the camera was, and it stays
    the score of the decision that was actually taken.
    """
    meeting = await resolve_meeting_for_session(session, attendance_session_id, on_date=on_date)
    if meeting is None:
        return None

    existing = (await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.meeting_id == meeting.id,
            AttendanceRecord.person_id == person_id,
        )
    )).scalar_one_or_none()

    if existing is not None:
        if existing.source == "face" and existing.status == "H":
            # A second scan in the same lesson: keep the best match seen, so the
            # page reports the strongest evidence rather than the last frame.
            if confidence is not None and (existing.match_score is None or confidence > existing.match_score):
                existing.match_score = confidence
            return meeting
        if existing.source == "manual":
            LOGGER.info(
                "face_attendance_kept_manual_status",
                extra={"meeting_id": str(meeting.id), "person_id": str(person_id), "status": existing.status},
            )
            return meeting
        existing.status = "H"
        existing.source = "face"
        existing.match_score = confidence
        return meeting

    session.add(
        AttendanceRecord(
            meeting_id=meeting.id,
            person_id=person_id,
            status="H",
            source="face",
            match_score=confidence,
        )
    )
    LOGGER.info(
        "face_attendance_recorded",
        extra={
            "meeting_id": str(meeting.id),
            "meeting_number": meeting.meeting_number,
            "person_id": str(person_id),
            "match_score": confidence,
        },
    )
    return meeting


async def backfill_from_logs(
    session: AsyncSession, *, since: date_type | None = None
) -> dict[str, int]:
    """Replay accepted face-recognition logs into the academic ledger.

    Scans taken while the bridge could not resolve a pertemuan (a jadwal with no
    meetings, a session no jadwal owned) left an audit log but no Hadir, so the
    recap showed nothing for them. This walks those logs and files them.

    Logs are grouped by session and by the WITA day they happened on, and the
    groups are replayed oldest first, so each teaching day claims the next
    pertemuan in order rather than everything piling onto meeting 1. Re-running
    is safe: a day already dated reuses its own meeting, and an existing status
    is left alone — only a missing match score is filled in, which is how rows
    filed before the score was carried across get theirs.
    """
    from db.domain.attendance import ATTENDANCE_SUCCESS_DECISIONS
    from db.models.entities import AttendanceLog

    statement = (
        select(
            AttendanceLog.session_id,
            AttendanceLog.person_id,
            AttendanceLog.created_at,
            AttendanceLog.confidence,
        )
        .where(
            AttendanceLog.is_deleted.is_(False),
            AttendanceLog.decision.in_(ATTENDANCE_SUCCESS_DECISIONS),
            AttendanceLog.session_id.isnot(None),
            AttendanceLog.person_id.isnot(None),
        )
        .order_by(AttendanceLog.created_at.asc())
    )
    rows = (await session.execute(statement)).all()

    # (session, WITA date) -> the students seen that day, each kept at the best
    # match the camera got for them: several scans of one lesson describe one
    # Hadir, and the strongest is the fairest evidence for it.
    groups: dict[tuple[UUID, date_type], dict[UUID, float | None]] = {}
    for session_id, person_id, created_at, confidence in rows:
        day = created_at.astimezone(WITA_TZ).date()
        if since is not None and day < since:
            continue
        people = groups.setdefault((session_id, day), {})
        if person_id not in people:
            people[person_id] = confidence
        elif confidence is not None and (people[person_id] is None or confidence > people[person_id]):
            people[person_id] = confidence

    recorded = 0
    scored = 0
    skipped_days = 0
    for (session_id, day), people in sorted(groups.items(), key=lambda item: item[0][1]):
        meeting = await resolve_meeting_for_session(session, session_id, on_date=day)
        if meeting is None:
            skipped_days += 1
            continue
        for person_id, confidence in people.items():
            existing = (await session.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.meeting_id == meeting.id,
                    AttendanceRecord.person_id == person_id,
                )
            )).scalar_one_or_none()
            if existing is not None:
                # The status stands as it is — a teacher may have corrected it.
                # Only a face row still missing its score is completed here.
                if existing.source == "face" and existing.match_score is None and confidence is not None:
                    existing.match_score = confidence
                    scored += 1
                continue
            session.add(
                AttendanceRecord(
                    meeting_id=meeting.id,
                    person_id=person_id,
                    status="H",
                    source="face",
                    match_score=confidence,
                )
            )
            recorded += 1
        await session.flush()

    LOGGER.info(
        "face_attendance_backfilled",
        extra={
            "days": len(groups),
            "recorded": recorded,
            "scored": scored,
            "skipped_days": skipped_days,
        },
    )
    return {
        "days": len(groups),
        "recorded": recorded,
        "scored": scored,
        "skipped_days": skipped_days,
    }
