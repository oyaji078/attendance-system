from __future__ import annotations

from alembic import op

revision = "20260501_0004"
down_revision = "20260501_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE device_configs
        SET
            min_face_width_px = 130,
            accepted_per_pose = 2,
            updated_at = now()
        WHERE device_code = 'web-kiosk-a01'
          AND min_face_width_px >= 150
          AND accepted_per_pose >= 3
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE device_configs
        SET
            min_face_width_px = 150,
            accepted_per_pose = 3,
            updated_at = now()
        WHERE device_code = 'web-kiosk-a01'
          AND min_face_width_px = 130
          AND accepted_per_pose = 2
        """
    )
