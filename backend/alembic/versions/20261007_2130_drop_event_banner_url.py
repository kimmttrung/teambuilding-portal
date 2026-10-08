"""Drop unused event cover image URL.

Revision ID: c5e91a04b7d2
Revises: a3f8c1d27e90
"""

import sqlalchemy as sa

from alembic import op

revision = "c5e91a04b7d2"
down_revision = "a3f8c1d27e90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ảnh bìa chỉ lưu được từ form BTC, không màn hình nào vẽ. Bỏ cột để API không còn nhận URL này.
    inspector = sa.inspect(op.get_bind())
    if "banner_url" in {column["name"] for column in inspector.get_columns("events")}:
        with op.batch_alter_table("events") as batch:
            batch.drop_column("banner_url")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "banner_url" not in {column["name"] for column in inspector.get_columns("events")}:
        op.add_column("events", sa.Column("banner_url", sa.String(512), nullable=True))
