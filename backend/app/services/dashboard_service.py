"""Dashboard BTC: một màn hình trả lời "đang ở đâu, còn thiếu gì trước khi công bố".

Không tự đếm lại những thứ module khác đã đếm — slot bay, giường theo giới, thống kê đăng ký,
email đều gọi service gốc. Chỉ thêm những con số chưa ai tính: tỉ lệ theo team, người chưa
được xếp ở từng chặng, và checklist trước khi công bố.
"""

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.timeutils import utcnow_iso
from app.models.audit import AuditLog
from app.models.enums import EventStatus, FlightDirection, RegistrationStatus
from app.models.event import Event
from app.models.flight import FlightAssignment
from app.models.gala import GalaLayout, GalaSeat, GalaSeatAssignment, GalaTable
from app.models.org import Team
from app.models.registration import Registration, RegistrationBusNeed
from app.models.transportation import Bus, BusAssignment, TripLeg
from app.models.user import User
from app.services import (
    accommodation_service,
    email_service,
    event_service,
    flight_service,
    gala_service,
    registration_service,
)

DIRECTION_LABELS = {FlightDirection.OUTBOUND: "Chiều đi", FlightDirection.RETURN: "Chiều về"}
RECENT_ACTIVITY_LIMIT = 12


def build_dashboard(db: Session, *, event: Event) -> dict[str, Any]:
    registrations = registration_service.get_stats(db, event_id=event.id)
    flights = _flights(db, event_id=event.id)
    buses = _buses(db, event_id=event.id)
    rooms = _rooms(db, event_id=event.id)
    emails = email_service.get_stats(db)
    checklist, ready = build_checklist(
        status=event.status,
        registrations=registrations,
        flights=flights,
        buses=buses,
        rooms=rooms,
        emails=emails,
    )

    return {
        "generated_at": utcnow_iso(),
        "event": _event(event),
        "registrations": registrations,
        "teams": _teams(db, event_id=event.id),
        "flights": flights,
        "buses": buses,
        "rooms": rooms,
        "gala": _gala(db, event_id=event.id),
        "emails": emails,
        "checklist": checklist,
        "ready_to_publish": ready,
        "recent_activity": _recent_activity(db, event_id=event.id),
    }


def _participant_filter(event_id: int) -> tuple:
    return (
        Registration.event_id == event_id,
        Registration.status == RegistrationStatus.SUBMITTED,
        Registration.is_participating.is_(True),
    )


# --- Kỳ và các bước chuyển trạng thái ---


def _event(event: Event) -> dict[str, Any]:
    current = EventStatus(event.status)
    order = list(EventStatus)
    next_statuses = [
        {
            "status": target.value,
            "label": event_service.status_label(target),
            "is_forward": order.index(target) > order.index(current),
            "requires_reason": (current, target) in event_service.TRANSITIONS_REQUIRING_REASON,
        }
        for target in event_service.ALLOWED_TRANSITIONS[current]
    ]
    # Bước tiến trước: đó là việc BTC làm hằng ngày, bước lùi là ngoại lệ.
    next_statuses.sort(key=lambda item: (not item["is_forward"], order.index(EventStatus(item["status"]))))

    return {
        "id": event.id,
        "code": event.code,
        "name": event.name,
        "destination": event.destination,
        "start_date": event.start_date,
        "end_date": event.end_date,
        "status": current.value,
        "status_label": event_service.status_label(current),
        "registration_closes_at": event.registration_closes_at,
        "is_published": current.at_least(EventStatus.INFORMATION_PUBLISHED),
        "next_statuses": next_statuses,
    }


# --- Theo team ---


def _teams(db: Session, *, event_id: int) -> list[dict[str, Any]]:
    """Tỉ lệ phản hồi và tham gia của từng team — để BTC biết nhắc team nào.

    Người chưa gán team gom vào một dòng riêng thay vì bỏ qua: bỏ đi thì tổng các team
    không khớp số tổng ở trên và BTC mất công đi tìm chênh lệch.
    """
    members = dict(
        db.execute(
            select(User.team_id, func.count(User.id))
            .where(User.is_active.is_(True))
            .group_by(User.team_id)
        ).all()
    )
    counts: dict[int | None, dict[str, int]] = {}
    for team_id, status, participating, count in db.execute(
        select(
            User.team_id,
            Registration.status,
            Registration.is_participating,
            func.count(Registration.id),
        )
        .join(User, User.id == Registration.user_id)
        .where(Registration.event_id == event_id, User.is_active.is_(True))
        .group_by(User.team_id, Registration.status, Registration.is_participating)
    ).all():
        bucket = counts.setdefault(team_id, {"submitted": 0, "participating": 0, "cancelled": 0})
        if status == RegistrationStatus.SUBMITTED:
            bucket["submitted"] += count
            if participating:
                bucket["participating"] += count
        elif status == RegistrationStatus.CANCELLED:
            bucket["cancelled"] += count

    teams = db.scalars(select(Team).where(Team.is_active.is_(True)).order_by(Team.name)).all()
    rows = [_team_row(team.id, team.code, team.name, team.color, members, counts) for team in teams]
    if members.get(None) or counts.get(None):
        rows.append(_team_row(None, None, "Chưa gán team", None, members, counts))
    return rows


def _team_row(team_id, code, name, color, members, counts) -> dict[str, Any]:
    total = members.get(team_id, 0)
    bucket = counts.get(team_id, {"submitted": 0, "participating": 0, "cancelled": 0})
    submitted = bucket["submitted"]
    cancelled = bucket["cancelled"]
    participating = bucket["participating"]
    return {
        "team_id": team_id,
        "code": code,
        "name": name,
        "color": color,
        "members": total,
        "submitted": submitted,
        "participating": participating,
        "not_participating": submitted - participating,
        "cancelled": cancelled,
        "not_submitted": max(total - submitted - cancelled, 0),
        "response_rate": round((submitted + cancelled) / total, 4) if total else 0.0,
        "participation_rate": round(participating / total, 4) if total else 0.0,
    }


# --- Tiến độ phân bổ ---


def _flights(db: Session, *, event_id: int) -> list[dict[str, Any]]:
    summary = flight_service.capacity_summary(db, event_id=event_id)
    participants = summary["participants"]

    people_with_flight = dict(
        db.execute(
            select(FlightAssignment.direction, func.count(func.distinct(FlightAssignment.registration_id)))
            .join(Registration, Registration.id == FlightAssignment.registration_id)
            .where(*_participant_filter(event_id))
            .group_by(FlightAssignment.direction)
        ).all()
    )

    return [
        {
            "direction": str(item["direction"]),
            "flights": item["flights"],
            "usable_capacity": item["usable_capacity"],
            "assigned": item["assigned"],
            "unassigned": max(participants - people_with_flight.get(item["direction"], 0), 0),
            "remaining": item["remaining"],
            "shortfall": item["shortfall"],
        }
        for item in summary["directions"]
    ]


def _buses(db: Session, *, event_id: int) -> list[dict[str, Any]]:
    """Mỗi chặng: bao nhiêu người cần xe, bao nhiêu ghế, đã xếp bao nhiêu."""
    demand = dict(
        db.execute(
            select(RegistrationBusNeed.trip_leg_id, func.count(RegistrationBusNeed.id))
            .join(Registration, Registration.id == RegistrationBusNeed.registration_id)
            .where(*_participant_filter(event_id), RegistrationBusNeed.needs_bus.is_(True))
            .group_by(RegistrationBusNeed.trip_leg_id)
        ).all()
    )
    fleet = {
        leg_id: (count, capacity or 0)
        for leg_id, count, capacity in db.execute(
            select(Bus.trip_leg_id, func.count(Bus.id), func.sum(Bus.capacity))
            .where(Bus.event_id == event_id)
            .group_by(Bus.trip_leg_id)
        ).all()
    }
    assigned = dict(
        db.execute(
            select(BusAssignment.trip_leg_id, func.count(func.distinct(BusAssignment.registration_id)))
            .join(Registration, Registration.id == BusAssignment.registration_id)
            .where(*_participant_filter(event_id))
            .group_by(BusAssignment.trip_leg_id)
        ).all()
    )

    legs = db.scalars(
        select(TripLeg).where(TripLeg.event_id == event_id).order_by(TripLeg.display_order)
    ).all()
    rows = []
    for leg in legs:
        need = demand.get(leg.id, 0)
        buses, capacity = fleet.get(leg.id, (0, 0))
        placed = assigned.get(leg.id, 0)
        rows.append(
            {
                "trip_leg_id": leg.id,
                "code": leg.code,
                "name": leg.name,
                "direction": leg.direction,
                "demand": need,
                "buses": buses,
                "capacity": capacity,
                "assigned": placed,
                "unassigned": max(need - placed, 0),
                "shortfall": max(need - capacity, 0),
            }
        )
    return rows


def _rooms(db: Session, *, event_id: int) -> dict[str, Any]:
    summary = accommodation_service.summary(db, event_id=event_id)
    return {
        key: summary[key]
        for key in ("participants", "assigned", "unassigned", "total_beds", "uncovered")
    }


def _gala(db: Session, *, event_id: int) -> dict[str, Any]:
    layout_ids = select(GalaLayout.id).where(GalaLayout.event_id == event_id)
    tables = db.scalar(
        select(func.count(GalaTable.id)).where(GalaTable.layout_id.in_(layout_ids))
    ) or 0
    seats = db.scalar(
        select(func.count(GalaSeat.id))
        .join(GalaTable, GalaTable.id == GalaSeat.table_id)
        .where(GalaTable.layout_id.in_(layout_ids))
    ) or 0
    assigned = db.scalar(
        select(func.count(GalaSeatAssignment.id))
        .join(GalaSeat, GalaSeat.id == GalaSeatAssignment.seat_id)
        .join(GalaTable, GalaTable.id == GalaSeat.table_id)
        .where(GalaTable.layout_id.in_(layout_ids))
    ) or 0
    configured = bool(db.scalar(select(func.count()).select_from(layout_ids.subquery())))
    result = {"configured": configured, "tables": tables, "seats": seats, "assigned": assigned}
    gaps = gala_service.seating_gaps(db, event_id=event_id)
    if gaps is not None:
        result.update(
            selection_status=gaps["selection_status"],
            teams_missing=len(gaps["teams_missing"]),
            participants=gaps["participants"],
            unseated=gaps["unseated"],
        )
    return result


# --- Checklist trước khi công bố ---


def build_checklist(
    *,
    status: str,
    registrations: dict[str, Any],
    flights: list[dict[str, Any]],
    buses: list[dict[str, Any]],
    rooms: dict[str, Any],
    emails: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    """Việc cần xong trước khi chuyển sang `information_published`.

    Hàm thuần (chỉ nhận số liệu) để test được từng tình huống mà không phải dựng DB.
    Không CHẶN công bố — BTC có thể cố ý công bố từng phần — chỉ nói rõ còn thiếu gì.
    """
    participants = registrations["participating"]
    missing_documents = registrations["missing_flight_documents"]

    capacity_gaps = [
        f"{DIRECTION_LABELS.get(item['direction'], item['direction'])} "
        + ("chưa có chuyến" if item["flights"] == 0 else f"thiếu {item['shortfall']} ghế")
        for item in flights
        if item["flights"] == 0 or item["shortfall"] > 0
    ]
    unassigned_flights = sum(item["unassigned"] for item in flights)
    bus_gaps = [f"{item['name']}: còn {item['unassigned']} người" for item in buses if item["unassigned"]]

    room_detail = None
    if rooms["unassigned"]:
        room_detail = f"Còn {rooms['unassigned']} người chưa có phòng"
        if rooms["uncovered"]:
            room_detail += f", {rooms['uncovered']} người không còn giường hợp lệ theo giới tính"

    items = [
        {
            "key": "registration_closed",
            "label": "Đóng đăng ký",
            "done": EventStatus(status).at_least(EventStatus.REGISTRATION_CLOSED),
            "detail": "CBNV vẫn sửa được đăng ký nên kết quả phân bổ có thể lạc hậu.",
            "link": None,
        },
        {
            "key": "flight_documents",
            "label": "Đủ giấy tờ để xuất vé",
            "done": missing_documents == 0,
            "detail": f"{missing_documents} người thiếu CCCD hoặc ngày sinh.",
            "link": "/admin/registrations?missing_documents=true",
        },
        {
            "key": "flight_capacity",
            "label": "Đủ ghế máy bay hai chiều",
            "done": bool(flights) and not capacity_gaps,
            "detail": "; ".join(capacity_gaps) or "Chưa khai chuyến bay nào.",
            "link": "/admin/flights",
        },
        {
            "key": "flights_assigned",
            "label": "Xếp chuyến bay cho mọi người",
            "done": participants > 0 and unassigned_flights == 0,
            "detail": (
                f"Còn {unassigned_flights} lượt bay chưa có chuyến."
                if participants
                else "Chưa có ai xác nhận tham gia."
            ),
            "link": "/admin/flights/board",
        },
        {
            "key": "buses_assigned",
            "label": "Xếp xe cho người cần xe",
            "done": not bus_gaps,
            "detail": "; ".join(bus_gaps),
            "link": "/admin/buses",
        },
        {
            "key": "rooms_assigned",
            "label": "Xếp phòng khách sạn",
            "done": participants > 0 and rooms["unassigned"] == 0,
            "detail": room_detail or ("Chưa có ai xác nhận tham gia." if not participants else None),
            "link": "/admin/rooms",
        },
        {
            "key": "emails_ok",
            "label": "Email gửi không lỗi",
            "done": emails["failed"] == 0,
            "required": False,
            "detail": f"{emails['failed']} email gửi lỗi — CBNV có thể không nhận được xác nhận.",
            "link": "/admin/email-logs?status=failed",
        },
    ]
    for item in items:
        item.setdefault("required", True)
        if item["done"]:
            item["detail"] = None

    ready = all(item["done"] for item in items if item["required"])
    return items, ready


# --- Nhật ký ---


def _recent_activity(db: Session, *, event_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.event_id == event_id)
        .order_by(AuditLog.id.desc())
        .limit(RECENT_ACTIVITY_LIMIT)
        .options(selectinload(AuditLog.actor))
    ).all()
    return [
        {
            "id": row.id,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "actor_name": row.actor.full_name if row.actor else None,
            "reason": row.reason,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def audit_row(entry: AuditLog) -> dict[str, Any]:
    """Một dòng nhật ký cho API: before/after đổi từ chuỗi JSON về object."""
    return {
        "id": entry.id,
        "event_id": entry.event_id,
        "actor_id": entry.actor_id,
        "actor_name": entry.actor.full_name if entry.actor else None,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "before": _decode(entry.before_data),
        "after": _decode(entry.after_data),
        "reason": entry.reason,
        "ip_address": entry.ip_address,
        "created_at": entry.created_at,
    }


def _decode(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        # Có chỗ ghi thẳng chuỗi thường (audit_service._serialize) — trả nguyên văn.
        return raw
