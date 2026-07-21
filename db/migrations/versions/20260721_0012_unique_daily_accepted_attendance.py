"""Enforce one accepted attendance per person/session/WITA-day at the database level.

The confirm flow guards duplicates with SELECT-then-INSERT
(``has_accepted_log_in_window``), which two concurrent requests can race past.
This partial unique index makes the database the source of truth for the
documented business rule (see ``RecognitionService.confirm_attendance``):

    business key = session_id + person_id + calendar day in WITA (UTC+8)

Only successful decisions participate (mirrors ``ATTENDANCE_SUCCESS_DECISIONS``)
and soft-deleted rows are excluded, matching ``has_accepted_log_in_window``.

WITA has no daylight saving time, so the day boundary is computed with an
immutable expression: ``((created_at AT TIME ZONE 'UTC') + INTERVAL '8 hours')::date``.

If pre-existing duplicate rows block index creation, this migration aborts with
a report of the conflicting keys. No data is deleted automatically — resolve
duplicates manually (e.g. soft-delete the extras via ``is_deleted = true``)
and re-run the migration.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260721_0012"
down_revision = "20260721_0011"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_attendance_logs_accepted_once_per_day"

_DUPLICATE_CHECK = """
SELECT session_id, person_id,
       (((created_at AT TIME ZONE 'UTC') + INTERVAL '8 hours')::date) AS wita_date,
       count(*) AS total
FROM attendance_logs
WHERE decision IN ('accepted', 'manual_approved', 'recognized')
  AND is_deleted = false
  AND session_id IS NOT NULL
  AND person_id IS NOT NULL
GROUP BY 1, 2, 3
HAVING count(*) > 1
LIMIT 20
"""


def upgrade() -> None:
    connection = op.get_bind()
    duplicates = connection.execute(sa.text(_DUPLICATE_CHECK)).fetchall()
    if duplicates:
        detail = "; ".join(
            f"session={row.session_id} person={row.person_id} day={row.wita_date} count={row.total}"
            for row in duplicates
        )
        raise RuntimeError(
            "Cannot create unique attendance index: duplicate accepted logs exist. "
            "Soft-delete the extra rows (is_deleted = true) and re-run. "
            f"Conflicts (first 20): {detail}"
        )
    op.execute(
        f"""
        CREATE UNIQUE INDEX {INDEX_NAME}
        ON attendance_logs (
            session_id,
            person_id,
            (((created_at AT TIME ZONE 'UTC') + INTERVAL '8 hours')::date)
        )
        WHERE decision IN ('accepted', 'manual_approved', 'recognized')
          AND is_deleted = false
          AND session_id IS NOT NULL
          AND person_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="attendance_logs")
