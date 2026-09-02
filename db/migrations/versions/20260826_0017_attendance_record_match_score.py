"""Keep the face-match score on the attendance row itself.

``attendance_logs.confidence`` already records how well a face matched, but the
log is the kiosk's audit trail: it is keyed by session and moment, not by
pertemuan, so the Absensi page could not show staff how sure the camera was
about a row without re-deriving the link on every read.

Copying the score onto ``attendance_records`` at the moment the scan is filed
keeps it stable — a later re-enrolment changes future matches but must not
rewrite the number the recorded decision was made on — and leaves NULL as the
honest value for anything a teacher entered by hand.

No backfill here: existing rows are filled by "Tarik Absensi Wajah" in the
console, which already walks the same logs.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260826_0017"
down_revision = "20260822_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendance_records", sa.Column("match_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("attendance_records", "match_score")
