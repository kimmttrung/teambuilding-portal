"""Email báo CBNV khi BTC đổi hành trình ĐÃ CÔNG BỐ của họ: chuyến bay, xe, phòng, ghế Gala.

Cách làm: chụp phần hành trình mỗi người đang thấy **trước** và **sau** thao tác của BTC rồi so.
Ai có dữ liệu của CHÍNH MÌNH đổi mới nhận thư, và thư chỉ nêu phần đổi — đúng người, đúng dịch
vụ. Nhờ so kết quả thay vì móc vào từng thao tác, mọi đường sửa (chuyển người, sửa giờ bay, đổi
biển số xe, xếp lại phòng, ép gán ghế Gala, chạy lại phân bổ, import Excel) dùng chung một cơ chế
và không sót ai: sửa giờ một chuyến bay thì đúng hành khách chuyến đó nhận thư.

Chỉ chạy khi kỳ đã công bố (CLAUDE.md cạm bẫy #6): trước đó CBNV chưa thấy gì, báo "đổi" là lộ
phân bổ dở dang. Chỉ chạy khi BTC tích "Gửi email" (`notify`) — mặc định không gửi.

Không đưa danh sách bạn cùng phòng vào phép so: người khác chuyển vào/ra phòng không làm hành
trình của mình đổi, gửi thư cho cả phòng mỗi lần xếp lại là spam.
"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.core.timeutils import format_vn
from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.audit import AuditLog
from app.models.enums import EventStatus, FlightDirection, RegistrationStatus
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment
from app.models.gala import GalaLayout, GalaSeat, GalaSeatAssignment, GalaTable
from app.models.registration import Registration
from app.models.transportation import Bus, BusAssignment, PickupPoint, TripLeg
from app.models.user import User
from app.services import audit_service, email_service, email_templates

logger = logging.getLogger(__name__)

TEMPLATE = "journey_changed"
RELATED_TYPE = "audit_log"
AUDIT_ACTION = "journey.notified"

Snapshot = dict[int, dict[str, dict[str, str]]]  # registration_id -> phần -> nhãn -> giá trị


class JourneyTracker:
    """Dùng trong router quanh một thao tác của BTC:

        tracker = JourneyTracker(db, event, notify=notify)   # chụp TRƯỚC
        ... gọi service (service tự commit) ...
        jobs = tracker.finish(actor=actor, action="flight.updated")  # chụp SAU, xếp thư, commit

    Không bật (`notify=False` hoặc kỳ chưa công bố) thì cả hai bước là no-op, không tốn truy vấn.
    """

    def __init__(self, db: Session, event: Event, *, notify: bool) -> None:
        self.db = db
        self.event_id = event.id
        self.enabled = bool(notify) and EventStatus(event.status).at_least(
            EventStatus.INFORMATION_PUBLISHED
        )
        self.before: Snapshot = snapshot(db, event.id) if self.enabled else {}

    def finish(
        self, *, actor: User, action: str, reason: str | None = None,
        ip_address: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        self.db.expire_all()  # service vừa commit ở transaction khác của cùng session
        after = snapshot(self.db, self.event_id)
        jobs = queue_changes(
            self.db, event_id=self.event_id, before=self.before, after=after, actor=actor,
            action=action, reason=reason, ip_address=ip_address,
        )
        self.db.commit()
        return jobs


# --- Chụp ---


def snapshot(db: Session, event_id: int) -> Snapshot:
    """Phần hành trình mỗi người tham gia đang thấy, đã dịch sẵn sang chữ để so và in vào thư."""
    result: Snapshot = {}

    def put(registration_id: int, part: str, fields: dict[str, str | None]) -> None:
        result.setdefault(registration_id, {})[part] = {
            label: value for label, value in fields.items() if value not in (None, "", "—")
        }

    for row, flight in db.execute(
        select(FlightAssignment, Flight)
        .join(Flight, Flight.id == FlightAssignment.flight_id)
        .where(Flight.event_id == event_id)
    ):
        part = (
            "Chuyến bay chiều đi"
            if row.direction == FlightDirection.OUTBOUND
            else "Chuyến bay chiều về"
        )
        put(row.registration_id, part, {
            "Chuyến bay": " · ".join(filter(None, [flight.flight_code, flight.airline])),
            "Hành trình": f"{flight.departure_airport} → {flight.arrival_airport}",
            "Cất cánh": _when(flight.departure_time),
            "Hạ cánh": _when(flight.arrival_time),
            "Số ghế": row.seat_number,
            "Mã vé": row.ticket_code,
        })

    leader = aliased(User)
    linked = aliased(Flight)
    for row, bus, leg, point, leader_user, linked_flight in db.execute(
        select(BusAssignment, Bus, TripLeg, PickupPoint, leader, linked)
        .join(Bus, Bus.id == BusAssignment.bus_id)
        .join(TripLeg, TripLeg.id == Bus.trip_leg_id)
        .outerjoin(PickupPoint, PickupPoint.id == Bus.pickup_point_id)
        .outerjoin(leader, leader.id == Bus.leader_user_id)
        .outerjoin(linked, linked.id == Bus.linked_flight_id)
        .where(Bus.event_id == event_id)
    ):
        leader_name = bus.leader_name or (leader_user.full_name if leader_user else None)
        leader_phone = bus.leader_phone or (leader_user.phone if leader_user else None)
        put(row.registration_id, f"Xe {leg.name}", {
            "Xe": " · ".join(filter(None, [bus.bus_code, bus.plate_number])),
            "Giờ tập trung": _when(bus.gather_time),
            "Giờ xuất phát": _when(bus.departure_time),
            "Điểm đón": " — ".join(filter(None, [point.name, point.address])) if point else None,
            "Điểm trả": bus.dropoff_point,
            "Trưởng xe": " · ".join(filter(None, [leader_name, leader_phone])) or None,
            "Tài xế": " · ".join(filter(None, [bus.driver_name, bus.driver_phone])) or None,
            "Nối chuyến bay": linked_flight.flight_code if linked_flight else None,
        })

    for row, room, hotel in db.execute(
        select(RoomAssignment, Room, Hotel)
        .join(Room, Room.id == RoomAssignment.room_id)
        .join(Hotel, Hotel.id == Room.hotel_id)
        .where(Hotel.event_id == event_id)
    ):
        room_detail = ", ".join(filter(None, [
            f"tầng {room.floor}" if room.floor else None, room.room_type,
        ]))
        put(row.registration_id, "Phòng khách sạn", {
            "Khách sạn": hotel.name,
            "Địa chỉ": hotel.address,
            "Nhận phòng": _when(hotel.check_in_at),
            "Trả phòng": _when(hotel.check_out_at),
            "Phòng": f"{room.room_number} ({room_detail})" if room_detail else room.room_number,
            "Trưởng phòng": "Bạn" if row.is_room_captain else None,
        })

    for row, seat, table, layout in db.execute(
        select(GalaSeatAssignment, GalaSeat, GalaTable, GalaLayout)
        .join(GalaSeat, GalaSeat.id == GalaSeatAssignment.seat_id)
        .join(GalaTable, GalaTable.id == GalaSeat.table_id)
        .join(GalaLayout, GalaLayout.id == GalaTable.layout_id)
        .where(GalaLayout.event_id == event_id, GalaSeatAssignment.registration_id.is_not(None))
    ):
        put(row.registration_id, "Gala Dinner", {
            "Sự kiện": " — ".join(filter(None, [layout.name, layout.venue])),
            "Bắt đầu": _when(layout.starts_at),
            "Bàn": " · ".join(filter(None, [table.table_code, table.table_name])),
            "Ghế": str(seat.seat_number),
        })

    return result


# --- So và xếp thư ---


def diff(before: dict[str, dict[str, str]], after: dict[str, dict[str, str]]) -> list[list[str]]:
    """[[nhãn, cũ, mới], …] cho MỘT người. Rỗng = hành trình của người đó không đổi."""
    changes: list[list[str]] = []
    for part in sorted(set(before) | set(after), key=_part_order):
        old, new = before.get(part), after.get(part)
        if old == new:
            continue
        if old is None:
            summary = new.get("Chuyến bay") or new.get("Xe") or new.get("Phòng") or new.get("Bàn")
            changes.append([part, "Chưa xếp", f"Đã xếp: {summary}" if summary else "Đã xếp"])
            continue
        if new is None:
            changes.append([part, _summary(old), "Đã bỏ xếp — Ban tổ chức sẽ báo lại"])
            continue
        for label in [*old, *[key for key in new if key not in old]]:
            if old.get(label) != new.get(label):
                changes.append([f"{part} · {label}", old.get(label), new.get(label)])
    return changes


def queue_changes(
    db: Session, *, event_id: int, before: Snapshot, after: Snapshot, actor: User,
    action: str, reason: str | None = None, ip_address: str | None = None,
) -> list[dict[str, Any]]:
    per_registration = {
        registration_id: changes
        for registration_id in set(before) | set(after)
        if (changes := diff(before.get(registration_id, {}), after.get(registration_id, {})))
    }
    if not per_registration:
        return []

    registrations = db.scalars(
        select(Registration).where(
            Registration.id.in_(per_registration),
            Registration.status == RegistrationStatus.SUBMITTED,
        )
    ).all()
    event = db.get(Event, event_id)
    audit = audit_service.log(
        db,
        action=AUDIT_ACTION,
        entity_type="event",
        entity_id=event_id,
        actor_id=actor.id,
        event_id=event_id,
        after={
            "trigger": action,
            "changes": {str(reg.user_id): per_registration[reg.id] for reg in registrations},
        },
        reason=reason,
        ip_address=ip_address,
    )
    db.flush()

    queued = []
    for registration in registrations:
        user = db.get(User, registration.user_id)
        if user is None or not user.is_active or not user.email:
            continue
        context = email_templates.journey_change_context(
            event=event, user=user, changes=per_registration[registration.id], reason=reason
        )
        entry = email_service.enqueue(
            db, template=TEMPLATE, to_email=user.email, context=context, user_id=user.id,
            related_type=RELATED_TYPE, related_id=audit.id,
        )
        queued.append((entry, context))
    db.flush()
    logger.info("%s: xếp %d email báo đổi hành trình", action, len(queued))
    return [{"log_id": entry.id, "context": context} for entry, context in queued]


def rebuild_email_context(db: Session, *, audit: AuditLog, user: User) -> dict | None:
    """Gửi lại thư lỗi: chỉ khi hành trình hiện tại của người đó vẫn là "sau thay đổi"."""

    event = db.get(Event, audit.event_id) if audit.event_id else None
    if event is None or not EventStatus(event.status).at_least(EventStatus.INFORMATION_PUBLISHED):
        return None
    changes = (json.loads(audit.after_data or "{}").get("changes") or {}).get(str(user.id))
    if not changes:
        return None
    registration = db.scalar(
        select(Registration).where(
            Registration.event_id == event.id,
            Registration.user_id == user.id,
            Registration.status == RegistrationStatus.SUBMITTED,
        )
    )
    if registration is None:
        return None
    current = snapshot(db, event.id).get(registration.id, {})
    for label, _old, new in changes:
        part, _, field = label.partition(" · ")
        if field and current.get(part, {}).get(field) != new:
            return None  # đã đổi tiếp sau thư này — nội dung thư không còn đúng
    return email_templates.journey_change_context(
        event=event, user=user, changes=changes, reason=audit.reason
    )


# --- Nội bộ ---


def _when(value: str | None) -> str | None:
    if not value:
        return None
    # Giờ dạng "HH:MM" (giờ tập trung nhập tay) giữ nguyên; ISO thì đổi sang giờ Việt Nam.
    return format_vn(value) if "T" in value else value


def _summary(fields: dict[str, str]) -> str:
    return fields.get("Chuyến bay") or fields.get("Xe") or fields.get("Phòng") or fields.get(
        "Bàn"
    ) or "Đã xếp"


def _part_order(part: str) -> tuple[int, str]:
    for index, prefix in enumerate(("Chuyến bay chiều đi", "Chuyến bay chiều về", "Xe", "Phòng", "Gala")):
        if part.startswith(prefix):
            return index, part
    return 9, part
