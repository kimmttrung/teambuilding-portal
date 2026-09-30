"""TẠM THỜI — tên các model đã bỏ ở schema v2 (35 -> 27 bảng), để app khởi động được trong lúc
chủ module viết lại service theo docs/15-task-assignment.md.

Import được, nhưng DÙNG là ném NotImplementedError kèm chỗ thay thế, nên endpoint chưa sửa trả 500
với thông báo rõ ràng thay vì làm cả app không chạy. Viết lại xong phần của mình thì xoá dòng import
từ module này. Khi `grep -r _removed_v1 app` rỗng thì xoá luôn file này.
"""

from typing import NoReturn

_REPLACEMENTS = {
    "EventSetting": "events.settings (dict {khoá: giá trị})",
    "Consent": "registrations.consent_version / consented_at / consent_ip / consent_user_agent",
    "RoomAssignment": "registrations.room_id / is_room_captain / room_mode / room_assigned_by / room_assigned_at / room_note",
    "RegistrationBusNeed": "RegistrationLeg (registration_legs.needs_bus / pickup_point_id / note)",
    "BusAssignment": "RegistrationLeg (registration_legs.bus_id / assignment_mode / assigned_by / assigned_at)",
    "GalaSeatHold": "GalaSeat (status='held', team_id, held_by, held_at, hold_expires_at)",
    "GalaSeatAssignment": "GalaSeat (status='taken', team_id, registration_id, confirmed_by, confirmed_at)",
    "ChatSession": "ChatMessage (user_id, event_id, conversation_id, conversation_title)",
    "Announcement": "Content (kind='announcement')",
    "PolicyDocument": "Content (kind='document', doc_type)",
}

# SQLAlchemy dò các thuộc tính này khi nhận một đối tượng lạ; phải báo lỗi rõ thay vì AttributeError.
_SQLALCHEMY_PROBES = {"__clause_element__", "__table__", "__mapper__", "__tablename__"}


class RemovedModel:
    """Vật giữ chỗ cho một model đã bỏ. Mọi cách dùng đều báo lỗi chỉ đường sang schema mới."""

    def __init__(self, name: str) -> None:
        self._name = name

    def _fail(self) -> NoReturn:
        raise NotImplementedError(
            f"{self._name} đã bỏ ở schema v2. Dùng {_REPLACEMENTS[self._name]}. "
            "Chủ module viết lại phần này theo docs/15-task-assignment.md."
        )

    def __getattr__(self, attr: str):
        if attr.startswith("__") and attr not in _SQLALCHEMY_PROBES:
            raise AttributeError(attr)
        self._fail()

    def __call__(self, *args, **kwargs) -> NoReturn:
        self._fail()

    # Cho phép chú thích kiểu như `RoomAssignment | None` hay `list[RoomAssignment]` lúc định nghĩa hàm.
    def __or__(self, other):
        return self

    __ror__ = __or__

    def __repr__(self) -> str:
        return f"<removed model {self._name}>"


EventSetting = RemovedModel("EventSetting")
Consent = RemovedModel("Consent")
RoomAssignment = RemovedModel("RoomAssignment")
RegistrationBusNeed = RemovedModel("RegistrationBusNeed")
BusAssignment = RemovedModel("BusAssignment")
GalaSeatHold = RemovedModel("GalaSeatHold")
GalaSeatAssignment = RemovedModel("GalaSeatAssignment")
ChatSession = RemovedModel("ChatSession")
Announcement = RemovedModel("Announcement")
PolicyDocument = RemovedModel("PolicyDocument")
