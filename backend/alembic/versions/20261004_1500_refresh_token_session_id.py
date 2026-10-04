"""Session id on refresh tokens so access tokens die with their session.

Revision ID: a3f8c1d27e90
Revises: 84e71bc092af
"""

import sqlalchemy as sa

from alembic import op

revision = "a3f8c1d27e90"
down_revision = "84e71bc092af"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable: phiên phát hành trước bản này không có mã phiên. Access token của các phiên đó cũng
    # không có claim `sid` nên bị từ chối — mọi người đăng nhập lại một lần sau khi nâng cấp.
    # Kiểm trước khi thêm: DB dựng bằng `Base.metadata.create_all` (test, DB dev tạo tay) đã có sẵn
    # cột và index này — thêm lần nữa là "duplicate column name" và cả chuỗi migration dừng lại.
    inspector = sa.inspect(op.get_bind())
    if "session_id" not in {column["name"] for column in inspector.get_columns("refresh_tokens")}:
        op.add_column("refresh_tokens", sa.Column("session_id", sa.String(64), nullable=True))
    if "ix_refresh_tokens_session_id" not in {
        index["name"] for index in inspector.get_indexes("refresh_tokens")
    }:
        op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_session_id", table_name="refresh_tokens")
    with op.batch_alter_table("refresh_tokens") as batch:
        batch.drop_column("session_id")
