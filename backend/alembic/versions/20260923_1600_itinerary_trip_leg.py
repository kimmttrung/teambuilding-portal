"""link itinerary items to a bus leg

Revision ID: 5f3a91c7d420
Revises: c41d7e2f9a55
Create Date: 2026-09-23 16:00:00.000000

Mốc "Tập trung tại điểm đón" chỉ có nghĩa với người ĐI XE chặng đó. Trước đây lịch trình chỉ
lọc theo `audience` (ca/team), nên hai người cùng ca 1 — một người đi xe, một người tự lái —
đều thấy mốc tập trung 04:30.

`trip_leg_id` NULL = mốc chung như cũ, không lọc gì thêm. Có giá trị = chỉ hiện với người có
xe (hoặc có đăng ký nhu cầu xe) ở chặng đó, và khi kỳ đã công bố thì giờ/địa điểm lấy từ xe
thật của chính họ thay vì giờ BTC gõ tay.

`ondelete=SET NULL`: xoá chặng thì mốc lịch trình trở lại "chung" chứ không biến mất — mất
một mốc trong timeline khó phát hiện hơn nhiều so với một mốc thừa.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f3a91c7d420'
down_revision: Union[str, Sequence[str], None] = 'c41d7e2f9a55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("itinerary_items") as batch:
        batch.add_column(sa.Column("trip_leg_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_itinerary_items_trip_leg_id",
            "trip_legs",
            ["trip_leg_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_itinerary_items_trip_leg_id", "itinerary_items", ["trip_leg_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_itinerary_items_trip_leg_id", table_name="itinerary_items")
    with op.batch_alter_table("itinerary_items") as batch:
        batch.drop_constraint("fk_itinerary_items_trip_leg_id", type_="foreignkey")
        batch.drop_column("trip_leg_id")
