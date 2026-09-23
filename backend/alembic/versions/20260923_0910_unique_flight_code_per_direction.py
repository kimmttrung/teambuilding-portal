"""unique flight code per direction

Revision ID: 8a1d4e77b2c9
Revises: 4c0fc9100968
Create Date: 2026-09-23 09:10:00.000000

Mã chuyến phải là duy nhất trong (kỳ, chiều). Ràng buộc cũ còn kèm `departure_time` nên
BTC thêm được hai chuyến VN1234 chiều đi khác giờ — lúc phân bổ không biết chuyến nào là
chuyến nào.

Không gỡ ràng buộc cũ: SQLite phải dựng lại bảng mới bỏ được UNIQUE khai trong CREATE TABLE,
mà dựng lại bảng bằng batch mode sẽ làm rơi 4 CHECK constraint của `flights` (SQLAlchemy không
phản chiếu được CHECK trên SQLite). Ràng buộc cũ yếu hơn ràng buộc mới nên để lại là vô hại.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a1d4e77b2c9'
down_revision: Union[str, Sequence[str], None] = '4c0fc9100968'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "uq_flights_event_code_direction"


def upgrade() -> None:
    """Upgrade schema."""
    _rename_existing_duplicates()
    op.create_index(
        INDEX_NAME, "flights", ["event_id", "flight_code", "direction"], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(INDEX_NAME, table_name="flights")


def _rename_existing_duplicates() -> None:
    """Đổi tên chuyến trùng đã lỡ tạo trước bản vá, để index dựng được.

    Xoá thì mất luôn phân bổ đang treo ở chuyến đó, còn dừng migration thì cả hệ thống
    không khởi động nổi (entrypoint chạy migration). Nên chuyến trùng thứ hai trở đi được
    đổi thành `VN1234-TRUNG2` và ghi ra log — BTC thấy ngay trên màn hình Chuyến bay và tự
    quyết giữ chuyến nào.
    """
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            "SELECT event_id, flight_code, direction FROM flights "
            "GROUP BY event_id, flight_code, direction HAVING COUNT(*) > 1"
        )
    ).all()

    for event_id, flight_code, direction in duplicates:
        ids = [
            row[0]
            for row in bind.execute(
                sa.text(
                    "SELECT id FROM flights WHERE event_id = :event_id "
                    "AND flight_code = :flight_code AND direction = :direction ORDER BY id"
                ),
                {"event_id": event_id, "flight_code": flight_code, "direction": direction},
            ).all()
        ]
        # Giữ nguyên chuyến tạo trước, đổi tên những chuyến tạo sau.
        for order, flight_id in enumerate(ids[1:], start=2):
            new_code = _free_code(bind, event_id, flight_code, direction, order)
            bind.execute(
                sa.text("UPDATE flights SET flight_code = :code WHERE id = :id"),
                {"code": new_code, "id": flight_id},
            )
            print(
                f"[migration] Chuyến #{flight_id} trùng mã {flight_code} ({direction}) "
                f"-> đổi thành {new_code}"
            )


def _free_code(bind, event_id: int, flight_code: str, direction: str, order: int) -> str:
    """`VN1234-TRUNG2`, thêm số cho tới khi không đụng mã nào đang có."""
    # flight_code dài tối đa 16 ký tự, cắt phần gốc để hậu tố luôn đủ chỗ.
    suffix = f"-T{order}"
    candidate = f"{flight_code[: 16 - len(suffix)]}{suffix}"
    attempt = order
    while bind.execute(
        sa.text(
            "SELECT 1 FROM flights WHERE event_id = :event_id AND flight_code = :code "
            "AND direction = :direction"
        ),
        {"event_id": event_id, "code": candidate, "direction": direction},
    ).first():
        attempt += 1
        suffix = f"-T{attempt}"
        candidate = f"{flight_code[: 16 - len(suffix)]}{suffix}"
    return candidate
