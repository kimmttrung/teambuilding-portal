"""allow gala seat assignment without team

Revision ID: 4c0fc9100968
Revises: 73f5d563dcab
Create Date: 2026-09-16 12:26:43.384053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c0fc9100968'
down_revision: Union[str, Sequence[str], None] = '73f5d563dcab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """`team_id` cho phép NULL: ghế BTC xếp cho người chưa thuộc team nào.

    Người tham gia không nằm trong team nào (tài khoản BTC, người mới chưa gán team) không được
    bốc thăm nên không team nào chọn ghế hộ họ. Không có ghế "không thuộc team" thì họ vĩnh viễn
    nằm trong `unseated` và kỳ không bao giờ chuyển sang `event_started` được.
    """
    with op.batch_alter_table('gala_seat_assignments', schema=None) as batch_op:
        batch_op.alter_column('team_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade() -> None:
    """Quay lại NOT NULL — ghế không thuộc team nào không biểu diễn được nữa nên phải gỡ.

    Người ngồi các ghế đó quay về trạng thái chưa có ghế, đúng như trước khi có tính năng này.
    """
    op.execute("DELETE FROM gala_seat_assignments WHERE team_id IS NULL")
    with op.batch_alter_table('gala_seat_assignments', schema=None) as batch_op:
        batch_op.alter_column('team_id',
               existing_type=sa.INTEGER(),
               nullable=False)
