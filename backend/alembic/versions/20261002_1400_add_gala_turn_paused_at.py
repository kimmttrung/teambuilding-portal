"""Persist Gala turn pause across workers and restarts.

Revision ID: 84e71bc092af
Revises: 7d2a9e41c027
"""

import sqlalchemy as sa

from alembic import op

revision = "84e71bc092af"
down_revision = "7d2a9e41c027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gala_layouts", sa.Column("turn_paused_at", sa.String(32), nullable=True))


def downgrade() -> None:
    # Tránh làm lượt/hold đang đóng băng hết hạn khi bỏ trạng thái pause.
    bind = op.get_bind()
    if bind.execute(
        sa.text("SELECT 1 FROM gala_layouts WHERE turn_paused_at IS NOT NULL LIMIT 1")
    ).first():
        raise RuntimeError("Tiếp tục hoặc kết thúc lượt Gala đang tạm dừng trước khi downgrade.")
    with op.batch_alter_table("gala_layouts") as batch:
        batch.drop_column("turn_paused_at")
