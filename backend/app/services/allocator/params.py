"""Tham số của thuật toán phân bổ.

Trọng số nằm trong `event_settings`, không nằm trong code (docs/05 §2): BTC đổi ưu tiên
giữa "giữ team" và "đúng ca nguyện vọng" bằng cách sửa hai con số qua API, không phải
sửa thuật toán rồi deploy lại giữa lúc đang phân bổ.
"""

from dataclasses import asdict, dataclass

# Khoá trong event_settings -> tên thuộc tính ở đây.
SETTING_KEYS = {
    "allocation.team_weight": "team_weight",
    "allocation.shift_weight": "shift_weight",
    "allocation.split_penalty": "split_penalty",
    "allocation.max_split_per_team": "max_split_per_team",
    "allocation.min_chunk_size": "min_chunk_size",
}

# Mọi lần chạy mặc định dùng seed này để hai lần chạy cho ra kết quả giống hệt —
# BTC phải đối chiếu được kết quả đã xem với kết quả đã ghi (docs/05 §3).
DEFAULT_SEED = 20261015


@dataclass(frozen=True)
class AllocationParams:
    # Thưởng mỗi cặp cùng team trên cùng chuyến. > shift_weight vì giữ team quan trọng hơn.
    team_weight: int = 10
    # Thưởng mỗi người được đúng ca nguyện vọng.
    shift_weight: int = 6
    # Phạt mỗi lần một team bị tách thêm một mảnh.
    split_penalty: int = 25
    # Số mảnh tối đa một team bị tách; vượt thì sinh flag error.
    max_split_per_team: int = 2
    # Mảnh tách ra không nên nhỏ hơn số này (tránh một người lạc lõng).
    min_chunk_size: int = 3
    # Chặn cứng số vòng cải thiện cục bộ để thời gian chạy luôn đoán được.
    local_search_iterations: int = 200

    @classmethod
    def from_settings(cls, settings: dict | None) -> "AllocationParams":
        """Dựng tham số từ `event_service.get_settings()`.

        Giá trị lạ hoặc thiếu thì dùng mặc định thay vì nổ: BTC gõ sai một ô cấu hình
        không được làm cả việc phân bổ đứng lại.
        """
        return cls(**_int_settings(settings, SETTING_KEYS))

    def as_dict(self) -> dict:
        return asdict(self)


# --- Xếp phòng (docs/05 §7) ---

ROOM_SETTING_KEYS = {
    "rooms.team_weight": "team_weight",
    "rooms.flight_weight": "flight_weight",
    "rooms.department_weight": "department_weight",
}


@dataclass(frozen=True)
class RoomAllocationParams:
    # Thưởng mỗi cặp ở chung phòng. Cùng team quan trọng nhất: bạn cùng phòng là người quen.
    team_weight: int = 10
    # Cùng chuyến bay chiều đi = đến khách sạn cùng giờ, nhận phòng cùng lúc.
    flight_weight: int = 4
    department_weight: int = 1
    # Số vòng cải thiện cục bộ tối đa; dừng sớm khi một vòng không đổi được gì.
    local_search_sweeps: int = 20

    @classmethod
    def from_settings(cls, settings: dict | None) -> "RoomAllocationParams":
        return cls(**_int_settings(settings, ROOM_SETTING_KEYS))

    def as_dict(self) -> dict:
        return asdict(self)


def _int_settings(settings: dict | None, keys: dict[str, str]) -> dict[str, int]:
    """Đọc các khoá số nguyên từ `event_service.get_settings()`.

    Giá trị lạ hoặc thiếu thì bỏ qua để dùng mặc định thay vì nổ: BTC gõ sai một ô cấu hình
    không được làm cả việc phân bổ đứng lại.
    """
    values: dict[str, int] = {}
    for key, field_name in keys.items():
        raw = (settings or {}).get(key)
        if isinstance(raw, dict):  # dạng {"value": ..., "description": ...}
            raw = raw.get("value")
        try:
            if raw is not None:
                values[field_name] = int(raw)
        except (TypeError, ValueError):
            continue
    return values
