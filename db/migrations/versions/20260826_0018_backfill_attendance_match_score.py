"""Fill the match score for attendance already on file.

0017 added the column; every row that predates it is NULL, so the Absensi log
and the dashboard's accuracy card open empty on an installation that has been
recording attendance for weeks. The scores exist — they are in
``attendance_logs`` — they were simply never carried across.

The join mirrors what the kiosk bridge does when it files a scan: the scan and
the record must belong to the same kiosk session (through the jadwal that owns
it), the same student, and the same WITA teaching day. Where several scans back
one Hadir the strongest is kept, which is the rule the bridge applies live.

Only the direct session <-> jadwal link is followed. Attendance filed through
the bridge's class fallback (a jadwal that owns no session) is left alone rather
than guessed at, since a class with several subjects would have its scans
attributed to whichever one this query happened to reach first. "Tarik Absensi
Wajah" in the console remains the catch-all for those.
"""

from __future__ import annotations

from alembic import op

revision = "20260826_0018"
down_revision = "20260826_0017"
branch_labels = None
depends_on = None

# Asia/Makassar is WITA, a fixed +08:00 with no DST — the same offset the
# application uses when it decides which day a scan belongs to.
BACKFILL = """
UPDATE attendance_records AS target
SET match_score = best.confidence
FROM (
    SELECT record.id AS record_id, MAX(log.confidence) AS confidence
    FROM attendance_records AS record
    JOIN schedule_meetings AS meeting ON meeting.id = record.meeting_id
    JOIN class_schedules AS schedule ON schedule.id = meeting.schedule_id
    JOIN attendance_logs AS log
      ON log.session_id = schedule.attendance_session_id
     AND log.person_id = record.person_id
     AND (log.created_at AT TIME ZONE 'Asia/Makassar')::date = meeting.meeting_date
    WHERE record.source = 'face'
      AND record.match_score IS NULL
      AND meeting.meeting_date IS NOT NULL
      AND log.is_deleted = false
      AND log.decision IN ('accepted', 'manual_approved', 'recognized')
      AND log.confidence IS NOT NULL
    GROUP BY record.id
) AS best
WHERE target.id = best.record_id
"""


def upgrade() -> None:
    op.execute(BACKFILL)


def downgrade() -> None:
    # The scores stay in attendance_logs either way, and there is no record of
    # which rows this filled, so undoing it would clear scores the live path
    # wrote too. Dropping the column is 0017's job.
    pass
