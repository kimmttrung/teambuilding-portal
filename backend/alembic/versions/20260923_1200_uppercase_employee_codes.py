"""uppercase employee codes

Revision ID: c41d7e2f9a55
Revises: b6c2f0d51a74
Create Date: 2026-09-23 12:00:00.000000

Mã nhân viên không phân biệt hoa/thường: từ nay `create/update` chuẩn hóa về chữ hoa
ngay khi ghi (`user_admin_service`), giống import Excel và import phòng đã làm. Migration
này upper-hóa mã cũ cho đồng nhất.

Dòng xung đột (upper xong đụng mã của người khác, ví dụ NV0001 và nv0001 cùng tồn tại):
giữ nguyên cả hai, in log để BTC gộp/xoá tay — không tự xoá dữ liệu, không chặn khởi động.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c41d7e2f9a55'
down_revision: Union[str, Sequence[str], None] = 'b6c2f0d51a74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, employee_code, email FROM users WHERE employee_code IS NOT NULL")
    ).all()

    taken = {code.upper() for _, code, _ in rows if code.upper() == code}
    skipped: list[tuple] = []
    for user_id, code, email in sorted(rows, key=lambda row: row[0]):
        upper = code.upper()
        if upper == code:
            continue
        if upper in taken:
            # Giữ dòng đang giữ mã (đã chữ hoa hoặc upper trước), dòng này giữ nguyên
            # để BTC gộp/xoá tay.
            skipped.append((user_id, code, email))
            continue
        bind.execute(
            sa.text("UPDATE users SET employee_code = :code WHERE id = :id"),
            {"code": upper, "id": user_id},
        )
        taken.add(upper)

    for user_id, code, email in skipped:
        print(
            f"[migration] users #{user_id} ({email}) giữ mã {code}: "
            f"upper thành {code.upper()} sẽ đụng người khác — BTC gộp/xoá tay"
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Không phục hồi được chữ thường ban đầu — dữ liệu đã chuẩn hóa là quyết định một chiều.
    pass
