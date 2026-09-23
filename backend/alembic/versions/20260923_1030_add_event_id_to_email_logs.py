"""add event id to email logs

Revision ID: b6c2f0d51a74
Revises: 8a1d4e77b2c9
Create Date: 2026-09-23 10:30:00.000000

Nhật ký email và ô Email trên Tổng quan phải theo kỳ đang chọn; trước đây `email_logs`
không có cột nào nói thư thuộc kỳ nào nên đổi sang TB2027 vẫn thấy thư của TB2026.

Thêm khoá ngoại trên SQLite phải dựng lại bảng, nên `copy_from` khai lại nguyên trạng bảng
cũ — thiếu nó thì CHECK `status IN (...)` biến mất sau khi dựng lại (SQLAlchemy không phản
chiếu được CHECK trên SQLite).

Backfill dòng cũ: suy từ bản ghi mà thư trỏ tới (`related_type`/`related_id`) khi suy được,
còn lại gán về kỳ mặc định (`events.is_active`) — mọi thư cũ đều sinh ra khi chỉ có một kỳ
đang chạy. Không suy được và cũng không có kỳ mặc định thì để NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6c2f0d51a74'
down_revision: Union[str, Sequence[str], None] = '8a1d4e77b2c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _old_table() -> sa.Table:
    """Bảng `email_logs` TRƯỚC bản vá, khai đủ để batch mode dựng lại không mất gì."""
    return sa.Table(
        "email_logs",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("to_email", sa.String(length=255), nullable=False),
        sa.Column("template", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("related_type", sa.String(length=64), nullable=True),
        sa.Column("related_id", sa.Integer(), nullable=True),
        sa.Column("sent_at", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_email_logs"),
        sa.CheckConstraint(
            "status IN ('queued', 'sent', 'failed')", name="ck_email_logs_status_valid"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_email_logs_user_id_users"
        ),
        sa.Index("ix_email_logs_status", "status"),
        sa.Index("ix_email_logs_template", "template"),
        sa.Index("ix_email_logs_user_id", "user_id"),
    )


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("email_logs", copy_from=_old_table()) as batch_op:
        batch_op.add_column(sa.Column("event_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_email_logs_event_id", ["event_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_email_logs_event_id_events", "events", ["event_id"], ["id"]
        )

    _backfill()


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("email_logs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_email_logs_event_id_events", type_="foreignkey")
        batch_op.drop_index("ix_email_logs_event_id")
        batch_op.drop_column("event_id")


def _backfill() -> None:
    bind = op.get_bind()

    # Thư gắn với một đăng ký: kỳ lấy thẳng từ đăng ký đó.
    bind.execute(
        sa.text(
            "UPDATE email_logs SET event_id = ("
            " SELECT r.event_id FROM registrations r WHERE r.id = email_logs.related_id"
            ") WHERE related_type = 'registration' AND related_id IS NOT NULL"
        )
    )
    # Thư huỷ đăng ký: qua bảng yêu cầu huỷ rồi tới đăng ký.
    bind.execute(
        sa.text(
            "UPDATE email_logs SET event_id = ("
            " SELECT r.event_id FROM registration_cancellations c"
            " JOIN registrations r ON r.id = c.registration_id WHERE c.id = email_logs.related_id"
            ") WHERE event_id IS NULL AND related_type = 'registration_cancellation'"
        )
    )
    # Thư báo đổi trạng thái / hành trình: audit log đã ghi sẵn kỳ.
    bind.execute(
        sa.text(
            "UPDATE email_logs SET event_id = ("
            " SELECT a.event_id FROM audit_logs a WHERE a.id = email_logs.related_id"
            ") WHERE event_id IS NULL AND related_type = 'audit_log'"
        )
    )
    # Thư nhắc việc và thông báo trỏ thẳng tới kỳ.
    bind.execute(
        sa.text(
            "UPDATE email_logs SET event_id = related_id "
            "WHERE event_id IS NULL AND related_type = 'event' "
            "AND related_id IN (SELECT id FROM events)"
        )
    )
    # Phần còn lại: kỳ mặc định, vì thư cũ đều sinh ra khi hệ thống mới có một kỳ.
    default_event = bind.execute(
        sa.text("SELECT id FROM events WHERE is_active = 1 ORDER BY id LIMIT 1")
    ).scalar()
    if default_event is not None:
        bind.execute(
            sa.text("UPDATE email_logs SET event_id = :event_id WHERE event_id IS NULL"),
            {"event_id": default_event},
        )
