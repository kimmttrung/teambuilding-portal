"""Gala Dinner: sơ đồ bàn ghế, bốc thăm thứ tự team, lượt chọn, giữ và xác nhận ghế.

Luồng (docs/02-architecture.md §5.4):

1. BTC bốc thăm → mỗi team một vị trí + quota (= số người tham gia của team). Seed được lưu.
   `GalaDrawOrder.quota` là ảnh chụp lúc bốc thăm, chỉ giữ để tra lại; mọi phép so "đủ ghế chưa"
   tính lại từ số người đang tham gia (`_live_quota`) để người huỷ / đăng ký lại được phản ánh ngay.
2. BTC mở chọn ghế → team ở vị trí 1 tới lượt, có hạn `turn_seconds`.
3. Trưởng nhóm của team đang tới lượt giữ ghế (`hold_seconds`) rồi xác nhận.
   Đủ quota hoặc hết giờ → tự chuyển lượt. Hết team → kết thúc.
4. Trưởng nhóm gán từng thành viên vào ghế đã xác nhận → hiện trên My Journey.

Chống tranh chấp: giữ/xác nhận chạy trong `BEGIN IMMEDIATE` + `UNIQUE(seat_id)` ở cả hai bảng hold
và assignment. Hold hết hạn và lượt hết giờ được dọn **lazy** mỗi lần đọc sơ đồ (và mỗi nhịp của
luồng SSE) — không cần tiến trình nền.

Quyền riêng tư (docs/09-security.md §4): ai cũng thấy ghế thuộc team nào, nhưng TÊN người ngồi chỉ
BTC và chính team đó thấy.
"""

import hashlib
import logging
import random
import secrets
from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import immediate_transaction
from app.core.exceptions import (
    AppError,
    CapacityExceededError,
    ConflictError,
    InvalidEventStatusError,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.timeutils import iso_in, utcnow_iso
from app.models.enums import (
    ADMIN_ROLES,
    DrawStatus,
    EventStatus,
    GalaSelectionStatus,
    RegistrationStatus,
)
from app.models.event import Event
from app.models.gala import (
    GalaDrawOrder,
    GalaLayout,
    GalaSeat,
    GalaSeatAssignment,
    GalaSeatHold,
    GalaTable,
)
from app.models.org import Team
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service, email_service, email_templates, event_service

logger = logging.getLogger(__name__)

LAYOUT_FIELDS = (
    "name", "venue", "starts_at", "stage_position", "grid_width", "grid_height",
    "turn_seconds", "hold_seconds",
)
TABLE_FIELDS = ("table_code", "table_name", "seat_count", "pos_x", "pos_y", "is_vip", "is_available")
DEFAULT_TURN_SECONDS = 300
DEFAULT_HOLD_SECONDS = 120
TURN_TEMPLATE = "gala_turn_started"
TURN_RELATED_TYPE = "gala_draw_order"


# --- Tra cứu ---


def find_layout(db: Session, event_id: int) -> GalaLayout | None:
    return db.scalar(select(GalaLayout).where(GalaLayout.event_id == event_id).order_by(GalaLayout.id))


def get_layout(db: Session, event_id: int) -> GalaLayout:
    layout = find_layout(db, event_id)
    if layout is None:
        raise NotFoundError("BTC chưa tạo sơ đồ Gala cho kỳ này.", code="GALA_NOT_CONFIGURED")
    return layout


def led_team(db: Session, user_id: int) -> Team | None:
    """Team mà người này là Trưởng nhóm (`teams.leader_user_id`)."""
    return db.scalar(
        select(Team)
        .where(Team.leader_user_id == user_id, Team.is_active.is_(True))
        .order_by(Team.id)
    )


def _ensure_not_cancelled(db: Session, *, event_id: int, user_id: int) -> None:
    """Người đã huỷ đăng ký mất mọi quyền Trưởng nhóm Gala ở kỳ này.

    Phòng thủ sâu cho việc gỡ `teams.leader_user_id` lúc huỷ (cancellation_service):
    kể cả khi sót dữ liệu cũ hay đua transaction, người đã huỷ vẫn không giữ/nhả,
    xác nhận hay gán ghế được nữa.
    """
    status = db.scalar(
        select(Registration.status).where(
            Registration.event_id == event_id, Registration.user_id == user_id
        )
    )
    if status == RegistrationStatus.CANCELLED:
        raise PermissionDeniedError("Đăng ký của bạn đã huỷ nên không thao tác Gala được nữa.")


def _seat_ids(layout_id: int):
    return (
        select(GalaSeat.id)
        .join(GalaTable, GalaTable.id == GalaSeat.table_id)
        .where(GalaTable.layout_id == layout_id)
    )


def _holds(
    db: Session,
    layout_id: int,
    *,
    team_id: int | None = None,
    expired_at: str | None = None,
    live_at: str | None = None,
) -> list[GalaSeatHold]:
    stmt = select(GalaSeatHold).where(GalaSeatHold.seat_id.in_(_seat_ids(layout_id)))
    if team_id is not None:
        stmt = stmt.where(GalaSeatHold.team_id == team_id)
    if expired_at is not None:
        stmt = stmt.where(GalaSeatHold.expires_at <= expired_at)
    if live_at is not None:
        stmt = stmt.where(GalaSeatHold.expires_at > live_at)
    return list(db.scalars(stmt.order_by(GalaSeatHold.seat_id)))


def _count_assignments(db: Session, layout_id: int, team_id: int | None = None) -> int:
    stmt = select(func.count(GalaSeatAssignment.id)).where(
        GalaSeatAssignment.seat_id.in_(_seat_ids(layout_id))
    )
    if team_id is not None:
        stmt = stmt.where(GalaSeatAssignment.team_id == team_id)
    return db.scalar(stmt) or 0


def _active_order(db: Session, layout_id: int) -> GalaDrawOrder | None:
    return db.scalar(
        select(GalaDrawOrder)
        .where(GalaDrawOrder.layout_id == layout_id, GalaDrawOrder.status == DrawStatus.ACTIVE)
        .order_by(GalaDrawOrder.draw_position)
    )


def _next_waiting(db: Session, layout_id: int) -> GalaDrawOrder | None:
    return db.scalar(
        select(GalaDrawOrder)
        .where(GalaDrawOrder.layout_id == layout_id, GalaDrawOrder.status == DrawStatus.WAITING)
        .order_by(GalaDrawOrder.draw_position)
    )


def _seat_in_layout(db: Session, layout_id: int, seat_id: int) -> GalaSeat:
    seat = db.scalar(
        select(GalaSeat)
        .join(GalaTable, GalaTable.id == GalaSeat.table_id)
        .where(GalaTable.layout_id == layout_id, GalaSeat.id == seat_id)
        .options(
            selectinload(GalaSeat.table),
            selectinload(GalaSeat.hold),
            selectinload(GalaSeat.assignment),
        )
    )
    if seat is None:
        raise NotFoundError(f"Không tìm thấy ghế #{seat_id} trong sơ đồ.", code="SEAT_NOT_FOUND")
    return seat


def _table_in_layout(db: Session, layout_id: int, table_id: int) -> GalaTable:
    table = db.scalar(
        select(GalaTable)
        .where(GalaTable.layout_id == layout_id, GalaTable.id == table_id)
        .options(selectinload(GalaTable.seats).selectinload(GalaSeat.assignment))
    )
    if table is None:
        raise NotFoundError(f"Không tìm thấy bàn #{table_id} trong sơ đồ.", code="TABLE_NOT_FOUND")
    return table


def _label(seat: GalaSeat) -> str:
    return f"{seat.table.table_code} – ghế {seat.seat_number}"


# --- Dọn lazy: hold hết hạn, lượt hết giờ ---


def refresh(db: Session, *, layout_id: int, jobs: list[dict[str, Any]]) -> bool:
    """Xoá hold hết hạn và kết thúc lượt đã hết giờ. Chỉ giành khoá ghi khi thật sự có việc.

    Lượt kế tiếp bắt đầu ở đây thì email báo Trưởng nhóm được thêm vào `jobs` — người gọi gửi sau
    khi transaction đã commit. Trả True nếu đã ghi gì đó.
    """
    now = utcnow_iso()
    expired = db.scalar(
        select(func.count(GalaSeatHold.id)).where(
            GalaSeatHold.seat_id.in_(_seat_ids(layout_id)), GalaSeatHold.expires_at <= now
        )
    )
    due = db.scalar(
        select(func.count(GalaDrawOrder.id)).where(
            GalaDrawOrder.layout_id == layout_id,
            GalaDrawOrder.status == DrawStatus.ACTIVE,
            GalaDrawOrder.turn_ends_at <= now,
        )
    )
    if not expired and not due:
        return False

    with immediate_transaction(db):
        now = utcnow_iso()  # nhận khoá có thể mất vài giây: lấy lại mốc
        for hold in _holds(db, layout_id, expired_at=now):
            db.delete(hold)
        db.flush()
        layout = db.get(GalaLayout, layout_id)
        order = _active_order(db, layout_id)
        # Kiểm tra lại trong khoá: request khác có thể vừa chuyển lượt.
        if layout is not None and order is not None and order.turn_ends_at and order.turn_ends_at <= now:
            _finish_turn(
                db, layout, order, status=DrawStatus.DONE, actor_id=None, trigger="timeout", jobs=jobs
            )
    return True


def _start_turn(db: Session, layout: GalaLayout, order: GalaDrawOrder, jobs: list[dict[str, Any]]) -> None:
    order.status = DrawStatus.ACTIVE
    order.turn_started_at = utcnow_iso()
    order.turn_ends_at = iso_in(seconds=layout.turn_seconds)
    _notify_turn(db, order, jobs)


def _notify_turn(db: Session, order: GalaDrawOrder, jobs: list[dict[str, Any]]) -> None:
    """Email cho Trưởng nhóm: tới lượt team chọn ghế.

    Dòng `queued` nằm trong transaction chuyển lượt — lượt không chuyển thì không có email. Gửi thật
    sau khi commit (`jobs`). Team chưa có Trưởng nhóm thì chỉ ghi cảnh báo: BTC thấy điều đó trên
    bảng thứ tự lượt.
    """
    team = db.get(Team, order.team_id)
    leader = db.get(User, team.leader_user_id) if team is not None and team.leader_user_id else None
    if leader is None or not leader.is_active or not leader.email:
        logger.warning("Team #%s tới lượt chọn ghế Gala nhưng không có Trưởng nhóm để báo", order.team_id)
        return
    db.flush()
    context = turn_email_context(db, order=order, leader=leader)
    entry = email_service.enqueue(
        db,
        template=TURN_TEMPLATE,
        to_email=leader.email,
        context=context,
        user_id=leader.id,
        related_type=TURN_RELATED_TYPE,
        related_id=order.id,
    )
    db.flush()
    jobs.append({"log_id": entry.id, "context": context})


def turn_email_context(db: Session, *, order: GalaDrawOrder, leader: User) -> dict[str, Any]:
    layout = db.get(GalaLayout, order.layout_id)
    event = db.get(Event, layout.event_id)
    team = db.get(Team, order.team_id)
    return email_templates.gala_turn_context(
        event=event,
        user=leader,
        team_name=team.name if team else f"Team #{order.team_id}",
        layout_name=layout.name,
        venue=layout.venue,
        draw_position=order.draw_position,
        quota=_live_quota(db, event_id=layout.event_id, team_id=order.team_id),
        confirmed=_count_assignments(db, layout.id, order.team_id),
        turn_ends_at=order.turn_ends_at,
    )


def rebuild_turn_email(db: Session, *, order_id: int, user: User) -> dict[str, Any] | None:
    """Context để gửi lại email báo lượt đã lỗi. None nếu lượt đó không còn diễn ra."""
    order = db.get(GalaDrawOrder, order_id)
    if order is None or order.status != DrawStatus.ACTIVE:
        return None
    if order.turn_ends_at and order.turn_ends_at <= utcnow_iso():
        return None
    team = db.get(Team, order.team_id)
    if team is None or team.leader_user_id != user.id:
        return None
    return turn_email_context(db, order=order, leader=user)


def _finish_turn(
    db: Session,
    layout: GalaLayout,
    order: GalaDrawOrder,
    *,
    status: DrawStatus,
    actor_id: int | None,
    trigger: str,
    jobs: list[dict[str, Any]],
    ip_address: str | None = None,
) -> GalaDrawOrder | None:
    """Kết thúc lượt: nhả ghế team đang giữ, mở lượt kế tiếp hoặc chốt nếu hết team."""
    released = _holds(db, layout.id, team_id=order.team_id)
    for hold in released:
        db.delete(hold)
    order.status = status
    if trigger != "timeout":
        order.turn_ends_at = utcnow_iso()  # ghi mốc kết thúc thật
    db.flush()

    following = _next_waiting(db, layout.id)
    if following is not None:
        _start_turn(db, layout, following, jobs)
    else:
        layout.selection_status = GalaSelectionStatus.FINALIZED

    audit_service.log(
        db,
        action="gala.turn_ended",
        entity_type="gala_layout",
        entity_id=layout.id,
        actor_id=actor_id,
        event_id=layout.event_id,
        after={
            "team_id": order.team_id,
            "status": str(status),
            "trigger": trigger,
            "released_holds": len(released),
            "next_team_id": following.team_id if following else None,
        },
        ip_address=ip_address,
    )
    return following


# --- Xem sơ đồ ---


def build_view(db: Session, *, event: Event, viewer: User, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    event_id = event.id
    viewer_id, viewer_role, viewer_team_id = viewer.id, viewer.role, viewer.team_id
    layout = get_layout(db, event_id)
    refresh(db, layout_id=layout.id, jobs=jobs)
    layout = get_layout(db, event_id)

    is_admin = viewer_role in ADMIN_ROLES
    leading = led_team(db, viewer_id)
    my_team_id = leading.id if leading else viewer_team_id
    now = utcnow_iso()
    teams = {team.id: team for team in db.scalars(select(Team))}

    tables = db.scalars(
        select(GalaTable)
        .where(GalaTable.layout_id == layout.id)
        .order_by(GalaTable.pos_y, GalaTable.pos_x, GalaTable.table_code)
        .options(
            selectinload(GalaTable.seats).selectinload(GalaSeat.hold),
            selectinload(GalaTable.seats)
            .selectinload(GalaSeat.assignment)
            .selectinload(GalaSeatAssignment.registration)
            .selectinload(Registration.user),
        )
    ).all()

    totals = Counter()
    table_views = []
    for table in tables:
        seat_views = []
        for seat in sorted(table.seats, key=lambda item: item.seat_number):
            view = _seat_view(
                seat, table, teams=teams, my_team_id=my_team_id, my_user_id=viewer_id,
                is_admin=is_admin, now=now,
            )
            totals[view["state"]] += 1
            seat_views.append(view)
        table_views.append(
            {
                "id": table.id,
                "table_code": table.table_code,
                "table_name": table.table_name,
                "seat_count": table.seat_count,
                "pos_x": table.pos_x,
                "pos_y": table.pos_y,
                "is_vip": table.is_vip,
                "is_available": table.is_available,
                "available_seats": sum(1 for view in seat_views if view["state"] == "available"),
                "seats": seat_views,
            }
        )

    draw = _draw_state(db, layout, teams=teams, now=now, include_seed=is_admin)
    held_total = totals["held_by_me"] + totals["held_by_other"]
    return {
        "layout": {
            "id": layout.id,
            "name": layout.name,
            "venue": layout.venue,
            "starts_at": layout.starts_at,
            "stage_position": layout.stage_position,
            "grid_width": layout.grid_width,
            "grid_height": layout.grid_height,
            "selection_status": layout.selection_status,
            "turn_seconds": layout.turn_seconds,
            "hold_seconds": layout.hold_seconds,
            "draw_seed": layout.draw_seed if is_admin else None,
        },
        "tables": table_views,
        "draw": draw,
        "my_team": _my_team(
            db, layout, draw, teams=teams, team_id=my_team_id, is_leader=leading is not None, now=now
        ),
        "totals": {
            "seats": sum(totals.values()),
            "available": totals["available"],
            "held": held_total,
            "taken": totals["taken"],
            "unavailable": totals["unavailable"],
        },
        "can_manage": is_admin,
        "server_time": now,
    }


def _seat_view(
    seat: GalaSeat,
    table: GalaTable,
    *,
    teams: dict[int, Team],
    my_team_id: int | None,
    my_user_id: int | None = None,
    is_admin: bool,
    now: str,
) -> dict[str, Any]:
    view: dict[str, Any] = {"id": seat.id, "seat_number": seat.seat_number, "state": "available"}
    assignment, hold = seat.assignment, seat.hold

    if assignment is not None:
        team = teams.get(assignment.team_id)
        view.update(
            state="taken",
            team_id=assignment.team_id,
            team_name=team.name if team else None,
            team_color=team.color if team else None,
        )
        occupant = (
            assignment.registration.user
            if assignment.registration is not None and assignment.registration.user is not None
            else None
        )
        # `team_id is not None`: người xem chưa có team cũng có `my_team_id = None` — thiếu vế này
        # thì họ đọc được tên mọi người ngồi ghế không thuộc team nào. Nhưng ghế của CHÍNH họ thì
        # vẫn phải thấy, không thì người chưa có team nhìn sơ đồ không biết mình ngồi đâu.
        same_team = assignment.team_id is not None and assignment.team_id == my_team_id
        is_mine = occupant is not None and my_user_id is not None and occupant.id == my_user_id
        if is_admin or same_team or is_mine:
            view["registration_id"] = assignment.registration_id
            if occupant is not None:
                view["occupant_name"] = occupant.full_name
    elif not seat.is_available or not table.is_available:
        view["state"] = "unavailable"
    elif hold is not None and hold.expires_at > now:
        team = teams.get(hold.team_id)
        mine = hold.team_id == my_team_id
        view.update(
            state="held_by_me" if mine else "held_by_other",
            team_id=hold.team_id,
            team_name=team.name if team else None,
            team_color=team.color if team else None,
            hold_expires_at=hold.expires_at if mine or is_admin else None,
        )
    return view


def _draw_state(
    db: Session, layout: GalaLayout, *, teams: dict[int, Team] | None = None, now: str | None = None,
    include_seed: bool = False,
) -> dict[str, Any]:
    now = now or utcnow_iso()
    teams = teams if teams is not None else {team.id: team for team in db.scalars(select(Team))}
    seat_ids = _seat_ids(layout.id)
    confirmed = dict(
        db.execute(
            select(GalaSeatAssignment.team_id, func.count(GalaSeatAssignment.id))
            .where(GalaSeatAssignment.seat_id.in_(seat_ids))
            .group_by(GalaSeatAssignment.team_id)
        ).all()
    )
    held = dict(
        db.execute(
            select(GalaSeatHold.team_id, func.count(GalaSeatHold.id))
            .where(GalaSeatHold.seat_id.in_(seat_ids), GalaSeatHold.expires_at > now)
            .group_by(GalaSeatHold.team_id)
        ).all()
    )
    orders = db.scalars(
        select(GalaDrawOrder).where(GalaDrawOrder.layout_id == layout.id).order_by(GalaDrawOrder.draw_position)
    ).all()
    # Tính lại quota chứ không đọc `order.quota`: xem `_live_quota`.
    quotas = _team_quotas(db, layout.event_id)

    leader_ids = [team.leader_user_id for team in teams.values() if team.leader_user_id]
    leaders = (
        dict(db.execute(select(User.id, User.full_name).where(User.id.in_(leader_ids), User.is_active.is_(True))).all())
        if leader_ids
        else {}
    )
    active = next((order for order in orders if order.status == DrawStatus.ACTIVE), None)
    total_seats = db.scalar(
        select(func.count(GalaSeat.id))
        .join(GalaTable, GalaTable.id == GalaSeat.table_id)
        .where(
            GalaTable.layout_id == layout.id,
            GalaTable.is_available.is_(True),
            GalaSeat.is_available.is_(True),
        )
    ) or 0
    return {
        "selection_status": layout.selection_status,
        "draw_seed": layout.draw_seed if include_seed else None,
        "active_team_id": active.team_id if active else None,
        "active_turn_ends_at": active.turn_ends_at if active else None,
        "orders": [
            {
                "position": order.draw_position,
                "team_id": order.team_id,
                "team_code": teams[order.team_id].code if order.team_id in teams else "",
                "team_name": teams[order.team_id].name if order.team_id in teams else f"Team #{order.team_id}",
                "team_color": teams[order.team_id].color if order.team_id in teams else None,
                "leader_name": leaders.get(teams[order.team_id].leader_user_id) if order.team_id in teams else None,
                "quota": quotas.get(order.team_id, 0),
                "confirmed": confirmed.get(order.team_id, 0),
                "held": held.get(order.team_id, 0),
                "remaining": max(
                    quotas.get(order.team_id, 0) - confirmed.get(order.team_id, 0) - held.get(order.team_id, 0), 0
                ),
                "status": order.status,
                "turn_started_at": order.turn_started_at,
                "turn_ends_at": order.turn_ends_at,
            }
            for order in orders
        ],
        "total_quota": sum(quotas.get(order.team_id, 0) for order in orders),
        "total_seats": total_seats,
        "unteamed_participants": _unteamed_participants(db, layout.event_id),
        "server_time": now,
    }


def _my_team(
    db: Session,
    layout: GalaLayout,
    draw: dict[str, Any],
    *,
    teams: dict[int, Team],
    team_id: int | None,
    is_leader: bool,
    now: str,
) -> dict[str, Any] | None:
    team = teams.get(team_id) if team_id else None
    if team is None:
        return None
    order = next((item for item in draw["orders"] if item["team_id"] == team.id), None)
    live = _holds(db, layout.id, team_id=team.id, live_at=now)
    is_turn = (
        layout.selection_status == GalaSelectionStatus.OPEN
        and draw["active_team_id"] == team.id
    )
    return {
        "team_id": team.id,
        "team_name": team.name,
        "team_color": team.color,
        "is_leader": is_leader,
        "draw_position": order["position"] if order else None,
        "status": order["status"] if order else None,
        "quota": order["quota"] if order else 0,
        "confirmed": order["confirmed"] if order else _count_assignments(db, layout.id, team.id),
        "held": len(live),
        "remaining": order["remaining"] if order else 0,
        "is_my_turn": is_turn,
        "turn_ends_at": order["turn_ends_at"] if order and is_turn else None,
        "hold_expires_at": min((hold.expires_at for hold in live), default=None),
    }


def draw_state(db: Session, *, event: Event, viewer: User, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    is_admin = viewer.role in ADMIN_ROLES
    layout = get_layout(db, event.id)
    refresh(db, layout_id=layout.id, jobs=jobs)
    return _draw_state(db, get_layout(db, event.id), include_seed=is_admin)


def _team_quotas(db: Session, event_id: int) -> dict[int, int]:
    rows = db.execute(
        select(User.team_id, func.count(Registration.id))
        .join(User, User.id == Registration.user_id)
        .join(Team, Team.id == User.team_id)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
            Team.is_active.is_(True),
        )
        .group_by(User.team_id)
    ).all()
    return {team_id: count for team_id, count in rows if count > 0}


def _live_quota(db: Session, *, event_id: int, team_id: int) -> int:
    """Quota thực tế của team = số người đang tham gia NGAY LÚC NÀY.

    `GalaDrawOrder.quota` chỉ là ảnh chụp lúc bốc thăm, không bao giờ tự đổi. Người huỷ đăng ký
    sau đó được `cancellation_service` trả ghế về sơ đồ, nên số ghế tụt xuống còn con số cũ thì
    đứng yên → sơ đồ báo "team chưa đủ ghế" vĩnh viễn dù không còn ai thiếu chỗ. Ngược lại, người
    huỷ rồi đăng ký lại phải làm quota tăng lại để BTC nhìn ra team nào cần xếp bù.
    Vì vậy mọi phép so "đủ ghế chưa" đều tính lại từ đầu, giống `seating_gaps`.
    """
    return _team_quotas(db, event_id).get(team_id, 0)


def _unteamed_participants(db: Session, event_id: int) -> int:
    return db.scalar(
        select(func.count(Registration.id))
        .join(User, User.id == Registration.user_id)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
            User.team_id.is_(None),
        )
    ) or 0


# --- Luồng thay đổi cho SSE ---


def change_signature(db: Session, *, event_id: int, jobs: list[dict[str, Any]]) -> str:
    """Dấu vân tay của mọi thứ vẽ lên sơ đồ. Đổi = client tải lại `/gala/layout`.

    Không chứa dữ liệu cá nhân và giống nhau với mọi người xem: phân quyền hiển thị nằm ở
    `build_view`, không nằm ở luồng SSE.
    """
    layout = find_layout(db, event_id)
    if layout is None:
        return "none"
    layout_id = layout.id
    refresh(db, layout_id=layout_id, jobs=jobs)
    seat_ids = _seat_ids(layout_id)
    parts = [
        db.execute(
            select(GalaLayout.selection_status, GalaLayout.updated_at, GalaLayout.draw_seed).where(
                GalaLayout.id == layout_id
            )
        ).all(),
        db.execute(
            select(
                GalaTable.id, GalaTable.table_code, GalaTable.table_name, GalaTable.seat_count,
                GalaTable.pos_x, GalaTable.pos_y, GalaTable.is_vip, GalaTable.is_available,
            )
            .where(GalaTable.layout_id == layout_id)
            .order_by(GalaTable.id)
        ).all(),
        db.execute(
            select(GalaSeat.id).where(GalaSeat.id.in_(seat_ids), GalaSeat.is_available.is_(False)).order_by(GalaSeat.id)
        ).all(),
        db.execute(
            select(
                GalaDrawOrder.team_id, GalaDrawOrder.draw_position, GalaDrawOrder.quota,
                GalaDrawOrder.status, GalaDrawOrder.turn_ends_at,
            )
            .where(GalaDrawOrder.layout_id == layout_id)
            .order_by(GalaDrawOrder.draw_position)
        ).all(),
        db.execute(
            select(GalaSeatHold.seat_id, GalaSeatHold.team_id, GalaSeatHold.expires_at)
            .where(GalaSeatHold.seat_id.in_(seat_ids))
            .order_by(GalaSeatHold.seat_id)
        ).all(),
        db.execute(
            select(GalaSeatAssignment.seat_id, GalaSeatAssignment.team_id, GalaSeatAssignment.registration_id)
            .where(GalaSeatAssignment.seat_id.in_(seat_ids))
            .order_by(GalaSeatAssignment.seat_id)
        ).all(),
        # Quota sống (`_live_quota`): người đăng ký lại không đụng vào ghế nào nhưng vẫn làm team
        # thiếu ghế trở lại — không có dòng này thì màn hình đang mở không biết mà tải lại.
        sorted(_team_quotas(db, event_id).items()),
    ]
    return hashlib.sha1(repr(parts).encode()).hexdigest()[:16]


# --- BTC: sơ đồ và bàn ---


def create_layout(
    db: Session, *, event: Event, data: dict[str, Any], actor: User, ip_address: str | None = None
) -> None:
    if find_layout(db, event.id) is not None:
        raise ConflictError("Kỳ này đã có sơ đồ Gala.", code="GALA_LAYOUT_EXISTS")

    settings = event_service.get_settings(db, event.id)
    values = {key: value for key, value in data.items() if value is not None}
    values.setdefault("turn_seconds", _setting_int(settings, "gala.turn_seconds", DEFAULT_TURN_SECONDS))
    values.setdefault("hold_seconds", _setting_int(settings, "gala.hold_seconds", DEFAULT_HOLD_SECONDS))
    layout = GalaLayout(event_id=event.id, selection_status=GalaSelectionStatus.CLOSED, **values)
    db.add(layout)
    db.flush()
    audit_service.log(
        db,
        action="gala.layout_created",
        entity_type="gala_layout",
        entity_id=layout.id,
        actor_id=actor.id,
        event_id=event.id,
        after=audit_service.snapshot(layout, LAYOUT_FIELDS),
        ip_address=ip_address,
    )
    db.commit()


def update_layout(
    db: Session, *, event: Event, data: dict[str, Any], actor: User, ip_address: str | None = None
) -> None:
    layout = get_layout(db, event.id)
    before = audit_service.snapshot(layout, LAYOUT_FIELDS)
    for field in ("name", "stage_position", "grid_width", "grid_height", "turn_seconds", "hold_seconds"):
        if field in data and data[field] is None:
            data.pop(field)

    width = data.get("grid_width", layout.grid_width)
    height = data.get("grid_height", layout.grid_height)
    outside = db.scalars(
        select(GalaTable.table_code).where(
            GalaTable.layout_id == layout.id, (GalaTable.pos_x >= width) | (GalaTable.pos_y >= height)
        )
    ).all()
    if outside:
        raise AppError(
            f"Lưới {width}×{height} không chứa được bàn {', '.join(outside)}. Dời bàn trước khi thu nhỏ lưới.",
            code="TABLE_OUT_OF_GRID",
            details={"tables": list(outside)},
        )

    for field, value in data.items():
        setattr(layout, field, value)
    after = audit_service.snapshot(layout, LAYOUT_FIELDS)
    if after != before:
        audit_service.log(
            db,
            action="gala.layout_updated",
            entity_type="gala_layout",
            entity_id=layout.id,
            actor_id=actor.id,
            event_id=event.id,
            before=before,
            after=after,
            ip_address=ip_address,
        )
    db.commit()


def create_table(
    db: Session, *, event: Event, data: dict[str, Any], actor: User, ip_address: str | None = None
) -> None:
    layout = get_layout(db, event.id)
    _ensure_table_code_free(db, layout.id, data["table_code"])
    _ensure_position(db, layout, data["pos_x"], data["pos_y"])

    table = GalaTable(layout_id=layout.id, is_available=True, **data)
    table.seats = [GalaSeat(seat_number=number) for number in range(1, data["seat_count"] + 1)]
    db.add(table)
    db.flush()
    audit_service.log(
        db,
        action="gala.table_created",
        entity_type="gala_table",
        entity_id=table.id,
        actor_id=actor.id,
        event_id=event.id,
        after=audit_service.snapshot(table, TABLE_FIELDS),
        ip_address=ip_address,
    )
    db.commit()


def update_table(
    db: Session,
    *,
    event: Event,
    table_id: int,
    data: dict[str, Any],
    actor: User,
    ip_address: str | None = None,
) -> None:
    layout = get_layout(db, event.id)
    table = _table_in_layout(db, layout.id, table_id)
    before = audit_service.snapshot(table, TABLE_FIELDS)
    data = {key: value for key, value in data.items() if value is not None or key == "table_name"}

    if "table_code" in data and data["table_code"] != table.table_code:
        _ensure_table_code_free(db, layout.id, data["table_code"])
    if "pos_x" in data or "pos_y" in data:
        _ensure_position(
            db, layout, data.get("pos_x", table.pos_x), data.get("pos_y", table.pos_y), exclude_table_id=table.id
        )

    confirmed = [seat for seat in table.seats if seat.assignment is not None]
    if data.get("is_available") is False and table.is_available and confirmed:
        raise ConflictError(
            f"Bàn {table.table_code} đã có {len(confirmed)} ghế thuộc team. Gỡ các ghế đó trước khi khoá bàn.",
            code="TABLE_HAS_ASSIGNMENTS",
            details={"confirmed_seats": len(confirmed)},
        )

    new_count = data.get("seat_count", table.seat_count)
    if new_count > table.seat_count:
        existing = {seat.seat_number for seat in table.seats}
        for number in range(1, new_count + 1):
            if number not in existing:
                table.seats.append(GalaSeat(seat_number=number))
    elif new_count < table.seat_count:
        removed = [seat for seat in table.seats if seat.seat_number > new_count]
        in_use = sorted(seat.seat_number for seat in removed if seat.assignment is not None)
        if in_use:
            raise ConflictError(
                f"Không bớt được: ghế {', '.join(map(str, in_use))} của bàn {table.table_code} đã thuộc team.",
                code="SEATS_IN_USE",
                details={"seat_numbers": in_use},
            )
        for seat in removed:
            table.seats.remove(seat)

    for field, value in data.items():
        setattr(table, field, value)
    db.flush()
    if data.get("is_available") is False:
        for hold in db.scalars(
            select(GalaSeatHold).join(GalaSeat, GalaSeat.id == GalaSeatHold.seat_id).where(GalaSeat.table_id == table.id)
        ):
            db.delete(hold)

    after = audit_service.snapshot(table, TABLE_FIELDS)
    if after != before:
        audit_service.log(
            db,
            action="gala.table_updated",
            entity_type="gala_table",
            entity_id=table.id,
            actor_id=actor.id,
            event_id=event.id,
            before=before,
            after=after,
            ip_address=ip_address,
        )
    db.commit()


def delete_table(
    db: Session, *, event: Event, table_id: int, actor: User, ip_address: str | None = None
) -> None:
    layout = get_layout(db, event.id)
    table = _table_in_layout(db, layout.id, table_id)
    confirmed = sum(1 for seat in table.seats if seat.assignment is not None)
    if confirmed:
        raise ConflictError(
            f"Bàn {table.table_code} đã có {confirmed} ghế thuộc team, không xoá được.",
            code="TABLE_HAS_ASSIGNMENTS",
            details={"confirmed_seats": confirmed},
        )
    before = audit_service.snapshot(table, TABLE_FIELDS)
    db.delete(table)
    audit_service.log(
        db,
        action="gala.table_deleted",
        entity_type="gala_table",
        entity_id=table_id,
        actor_id=actor.id,
        event_id=event.id,
        before=before,
        ip_address=ip_address,
    )
    db.commit()


def _ensure_table_code_free(db: Session, layout_id: int, code: str) -> None:
    taken = db.scalar(
        select(func.count(GalaTable.id)).where(
            GalaTable.layout_id == layout_id, func.lower(GalaTable.table_code) == code.lower()
        )
    )
    if taken:
        raise ConflictError(f"Mã bàn {code} đã có trong sơ đồ.", code="TABLE_CODE_TAKEN")


def _ensure_position(
    db: Session, layout: GalaLayout, pos_x: int, pos_y: int, *, exclude_table_id: int | None = None
) -> None:
    if pos_x >= layout.grid_width or pos_y >= layout.grid_height:
        raise AppError(
            f"Vị trí ({pos_x}, {pos_y}) nằm ngoài lưới {layout.grid_width}×{layout.grid_height}.",
            code="TABLE_OUT_OF_GRID",
        )
    stmt = select(GalaTable.table_code).where(
        GalaTable.layout_id == layout.id, GalaTable.pos_x == pos_x, GalaTable.pos_y == pos_y
    )
    if exclude_table_id is not None:
        stmt = stmt.where(GalaTable.id != exclude_table_id)
    occupied = db.scalar(stmt)
    if occupied:
        raise ConflictError(f"Ô ({pos_x}, {pos_y}) đã có bàn {occupied}.", code="TABLE_POSITION_TAKEN")


def _setting_int(settings: dict[str, dict], key: str, default: int) -> int:
    try:
        return int(settings.get(key, {}).get("value", default))
    except (TypeError, ValueError):
        return default


# --- BTC: bốc thăm và điều khiển lượt ---


def draw(db: Session, *, event: Event, actor: User, seed: int | None = None, ip_address: str | None = None) -> None:
    event_id, actor_id = event.id, actor.id
    with immediate_transaction(db):
        layout = get_layout(db, event_id)
        if layout.selection_status not in (GalaSelectionStatus.CLOSED, GalaSelectionStatus.DRAWING):
            raise ConflictError(
                "Các team đã bắt đầu chọn ghế — không bốc thăm lại được.", code="GALA_DRAW_LOCKED"
            )
        confirmed = _count_assignments(db, layout.id)
        if confirmed:
            raise ConflictError(
                f"Đã có {confirmed} ghế thuộc team. Gỡ các ghế đó trước khi bốc thăm lại.",
                code="GALA_DRAW_LOCKED",
                details={"confirmed": confirmed},
            )

        quotas = _team_quotas(db, event_id)
        if not quotas:
            raise AppError("Chưa team nào có người tham gia để bốc thăm.", code="GALA_NO_TEAMS")

        used_seed = seed if seed is not None else secrets.randbelow(2_147_483_646) + 1
        order = sorted(quotas)  # sắp trước khi xáo: cùng seed + cùng danh sách team = cùng kết quả
        random.Random(used_seed).shuffle(order)

        for old in db.scalars(select(GalaDrawOrder).where(GalaDrawOrder.layout_id == layout.id)):
            db.delete(old)
        db.flush()
        for position, team_id in enumerate(order, start=1):
            db.add(
                GalaDrawOrder(
                    layout_id=layout.id,
                    team_id=team_id,
                    draw_position=position,
                    quota=quotas[team_id],
                    status=DrawStatus.WAITING,
                )
            )
        layout.selection_status = GalaSelectionStatus.DRAWING
        layout.draw_seed = used_seed
        audit_service.log(
            db,
            action="gala.drawn",
            entity_type="gala_layout",
            entity_id=layout.id,
            actor_id=actor_id,
            event_id=event_id,
            after={"seed": used_seed, "team_order": order, "quotas": {str(key): value for key, value in quotas.items()}},
            ip_address=ip_address,
        )
    logger.info("Bốc thăm Gala kỳ #%s: %s team, seed %s", event_id, len(order), used_seed)


def advance_turn(
    db: Session,
    *,
    event: Event,
    actor: User,
    jobs: list[dict[str, Any]],
    skip: bool = False,
    ip_address: str | None = None,
) -> None:
    """Chưa mở → mở chọn ghế, team số 1 tới lượt. Đang mở → kết thúc lượt hiện tại, chuyển team kế."""
    event_id, event_status, actor_id = event.id, event.status, actor.id
    with immediate_transaction(db):
        layout = get_layout(db, event_id)
        status = layout.selection_status
        if status == GalaSelectionStatus.CLOSED:
            raise ConflictError("Chưa bốc thăm thứ tự team.", code="GALA_NOT_DRAWN")
        if status == GalaSelectionStatus.FINALIZED:
            raise ConflictError("Việc chọn ghế đã kết thúc.", code="GALA_FINALIZED")

        if status == GalaSelectionStatus.DRAWING:
            _ensure_published(event_status)
            first = _next_waiting(db, layout.id)
            if first is None:
                raise ConflictError("Chưa bốc thăm thứ tự team.", code="GALA_NOT_DRAWN")
            _start_turn(db, layout, first, jobs)
            layout.selection_status = GalaSelectionStatus.OPEN
            audit_service.log(
                db,
                action="gala.selection_opened",
                entity_type="gala_layout",
                entity_id=layout.id,
                actor_id=actor_id,
                event_id=event_id,
                after={"team_id": first.team_id, "turn_ends_at": first.turn_ends_at},
                ip_address=ip_address,
            )
            return

        current = _active_order(db, layout.id)
        if current is not None:
            _finish_turn(
                db,
                layout,
                current,
                status=DrawStatus.SKIPPED if skip else DrawStatus.DONE,
                actor_id=actor_id,
                trigger="admin_skip" if skip else "admin",
                jobs=jobs,
                ip_address=ip_address,
            )
            return

        following = _next_waiting(db, layout.id)
        if following is not None:
            _start_turn(db, layout, following, jobs)
        else:
            layout.selection_status = GalaSelectionStatus.FINALIZED


def finalize(db: Session, *, event: Event, actor: User, ip_address: str | None = None) -> None:
    event_id, actor_id = event.id, actor.id
    with immediate_transaction(db):
        layout = get_layout(db, event_id)
        if layout.selection_status == GalaSelectionStatus.FINALIZED:
            raise ConflictError("Việc chọn ghế đã kết thúc.", code="GALA_FINALIZED")
        released = _holds(db, layout.id)
        for hold in released:
            db.delete(hold)
        current = _active_order(db, layout.id)
        if current is not None:
            current.status = DrawStatus.DONE
            current.turn_ends_at = utcnow_iso()
        layout.selection_status = GalaSelectionStatus.FINALIZED
        audit_service.log(
            db,
            action="gala.selection_finalized",
            entity_type="gala_layout",
            entity_id=layout.id,
            actor_id=actor_id,
            event_id=event_id,
            after={"released_holds": len(released)},
            ip_address=ip_address,
        )


# --- Trưởng nhóm: giữ, nhả, xác nhận ---


def _turn_context(db: Session, *, event_id: int, user_id: int) -> tuple[GalaLayout, GalaDrawOrder, Team]:
    layout = get_layout(db, event_id)
    if layout.selection_status != GalaSelectionStatus.OPEN:
        raise ConflictError(
            "Chưa tới giờ chọn ghế Gala, hoặc việc chọn ghế đã kết thúc.",
            code="GALA_SELECTION_CLOSED",
            details={"selection_status": layout.selection_status},
        )
    _ensure_not_cancelled(db, event_id=event_id, user_id=user_id)
    team = led_team(db, user_id)
    if team is None:
        raise PermissionDeniedError("Chỉ Trưởng nhóm mới chọn ghế Gala cho team.")

    order = _active_order(db, layout.id)
    if order is None or order.team_id != team.id:
        active_name = order.team.name if order is not None and order.team else None
        raise ConflictError(
            f"Chưa tới lượt team {team.name}." + (f" Đang tới lượt {active_name}." if active_name else ""),
            code="NOT_YOUR_TURN",
            details={"active_team_id": order.team_id if order else None},
        )
    if order.turn_ends_at and order.turn_ends_at <= utcnow_iso():
        raise ConflictError("Lượt chọn của team đã hết giờ.", code="TURN_EXPIRED")
    return layout, order, team


def hold_seats(
    db: Session, *, event: Event, user: User, seat_ids: list[int]
) -> dict[str, Any]:
    event_id, user_id = event.id, user.id
    wanted = sorted(set(seat_ids))
    try:
        with immediate_transaction(db):
            layout, order, team = _turn_context(db, event_id=event_id, user_id=user_id)
            now = utcnow_iso()
            for hold in _holds(db, layout.id, expired_at=now):
                db.delete(hold)
            db.flush()

            seats = db.scalars(
                select(GalaSeat)
                .join(GalaTable, GalaTable.id == GalaSeat.table_id)
                .where(GalaTable.layout_id == layout.id, GalaSeat.id.in_(wanted))
                .options(
                    selectinload(GalaSeat.table),
                    selectinload(GalaSeat.hold),
                    selectinload(GalaSeat.assignment),
                )
            ).all()
            missing = sorted(set(wanted) - {seat.id for seat in seats})
            if missing:
                raise NotFoundError(
                    "Có ghế không thuộc sơ đồ này.", code="SEAT_NOT_FOUND", details={"seat_ids": missing}
                )

            conflicts = []
            for seat in seats:
                if seat.assignment is not None:
                    conflicts.append((seat, "SEAT_TAKEN", "đã thuộc team khác"))
                elif not seat.is_available or not seat.table.is_available:
                    conflicts.append((seat, "SEAT_UNAVAILABLE", "không khả dụng"))
                elif seat.hold is not None and seat.hold.team_id != team.id:
                    conflicts.append((seat, "SEAT_HELD", "đang được team khác giữ"))
            if conflicts:
                seat, code, reason = conflicts[0]
                raise ConflictError(
                    f"{_label(seat)} {reason}. Tải lại sơ đồ rồi chọn ghế khác.",
                    code=code,
                    details={"seats": [{"seat_id": item.id, "code": item_code} for item, item_code, _ in conflicts]},
                )

            quota = _live_quota(db, event_id=event_id, team_id=team.id)
            confirmed = _count_assignments(db, layout.id, team.id)
            held = len(_holds(db, layout.id, team_id=team.id))
            new_seats = [seat for seat in seats if seat.hold is None]
            if confirmed + held + len(new_seats) > quota:
                remaining = max(quota - confirmed - held, 0)
                raise CapacityExceededError(
                    f"Team {team.name} chỉ còn chọn được {remaining} ghế (quota {quota}).",
                    code="GALA_QUOTA_EXCEEDED",
                    details={"quota": quota, "confirmed": confirmed, "held": held, "requested": len(new_seats)},
                )

            # Hạn giữ không vượt quá giờ hết lượt: đồng hồ trên màn hình phải nói thật.
            expires_at = min(iso_in(seconds=layout.hold_seconds), order.turn_ends_at or iso_in(seconds=layout.hold_seconds))
            for seat in seats:
                if seat.hold is not None:
                    seat.hold.expires_at = expires_at
                    seat.hold.held_by = user_id
                else:
                    db.add(
                        GalaSeatHold(
                            seat_id=seat.id, team_id=team.id, held_by=user_id, held_at=now, expires_at=expires_at
                        )
                    )
            held_after = held + len(new_seats)
            result = {
                "seat_ids": wanted,
                "expires_at": expires_at,
                "quota": quota,
                "confirmed": confirmed,
                "held": held_after,
                "remaining": max(quota - confirmed - held_after, 0),
            }
    except IntegrityError as exc:
        raise ConflictError(
            "Ghế vừa được team khác giữ. Tải lại sơ đồ rồi chọn ghế khác.", code="SEAT_HELD"
        ) from exc
    return result


def release_holds(db: Session, *, event: Event, user: User, seat_ids: list[int] | None = None) -> int:
    event_id, user_id = event.id, user.id
    with immediate_transaction(db):
        layout = get_layout(db, event_id)
        _ensure_not_cancelled(db, event_id=event_id, user_id=user_id)
        team = led_team(db, user_id)
        if team is None:
            raise PermissionDeniedError("Chỉ Trưởng nhóm mới nhả ghế của team.")
        holds = _holds(db, layout.id, team_id=team.id)
        if seat_ids:
            wanted = set(seat_ids)
            holds = [hold for hold in holds if hold.seat_id in wanted]
        for hold in holds:
            db.delete(hold)
        released = len(holds)
    return released


def confirm_seats(
    db: Session, *, event: Event, user: User, jobs: list[dict[str, Any]], ip_address: str | None = None
) -> dict[str, Any]:
    event_id, user_id = event.id, user.id
    try:
        with immediate_transaction(db):
            layout, order, team = _turn_context(db, event_id=event_id, user_id=user_id)
            now = utcnow_iso()
            for hold in _holds(db, layout.id, expired_at=now):
                db.delete(hold)
            db.flush()

            holds = _holds(db, layout.id, team_id=team.id)
            if not holds:
                raise ConflictError(
                    "Team chưa giữ ghế nào, hoặc ghế giữ đã hết hạn.", code="NO_ACTIVE_HOLDS"
                )
            quota = _live_quota(db, event_id=event_id, team_id=team.id)
            confirmed_before = _count_assignments(db, layout.id, team.id)
            if confirmed_before + len(holds) > quota:
                raise CapacityExceededError(
                    f"Vượt quota {quota} ghế của team.", code="GALA_QUOTA_EXCEEDED"
                )

            seat_ids = [hold.seat_id for hold in holds]
            for hold in holds:
                db.delete(hold)
            db.flush()
            for seat_id in seat_ids:
                db.add(
                    GalaSeatAssignment(
                        seat_id=seat_id, team_id=team.id, confirmed_by=user_id, confirmed_at=now
                    )
                )
            db.flush()

            total = confirmed_before + len(seat_ids)
            audit_service.log(
                db,
                action="gala.seats_confirmed",
                entity_type="gala_layout",
                entity_id=layout.id,
                actor_id=user_id,
                event_id=event_id,
                after={"team_id": team.id, "seat_ids": seat_ids, "confirmed_total": total, "quota": quota},
                ip_address=ip_address,
            )

            following = None
            finished = total >= quota
            if finished:
                following = _finish_turn(
                    db, layout, order, status=DrawStatus.DONE, actor_id=user_id, trigger="quota_filled",
                    jobs=jobs, ip_address=ip_address,
                )
            result = {
                "seat_ids": seat_ids,
                "confirmed_total": total,
                "quota": quota,
                "turn_finished": finished,
                "next_team_id": following.team_id if following else None,
            }
    except IntegrityError as exc:
        raise ConflictError("Có ghế vừa bị chiếm. Tải lại sơ đồ.", code="SEAT_TAKEN") from exc
    return result


# --- Gán người vào ghế ---


def team_members(db: Session, *, event: Event, viewer: User, team_id: int | None = None) -> list[dict[str, Any]]:
    """Thành viên tham gia của một team kèm ghế Gala. Trưởng nhóm: team mình; BTC: team bất kỳ."""
    if viewer.role in ADMIN_ROLES:
        if team_id is None:
            raise AppError("Chọn team cần xem.", code="TEAM_REQUIRED")
        target = team_id
    else:
        _ensure_not_cancelled(db, event_id=event.id, user_id=viewer.id)
        team = led_team(db, viewer.id)
        if team is None:
            raise PermissionDeniedError("Chỉ Trưởng nhóm mới xem được danh sách chỗ ngồi của team.")
        target = team.id

    layout = find_layout(db, event.id)
    seats: dict[int, tuple[int, str, int]] = {}
    if layout is not None:
        for assignment, table_code, seat_number in db.execute(
            select(GalaSeatAssignment, GalaTable.table_code, GalaSeat.seat_number)
            .join(GalaSeat, GalaSeat.id == GalaSeatAssignment.seat_id)
            .join(GalaTable, GalaTable.id == GalaSeat.table_id)
            .where(GalaTable.layout_id == layout.id, GalaSeatAssignment.registration_id.is_not(None))
        ):
            seats[assignment.registration_id] = (assignment.seat_id, table_code, seat_number)

    registrations = db.scalars(
        select(Registration)
        .join(User, User.id == Registration.user_id)
        .where(
            Registration.event_id == event.id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
            User.team_id == target,
        )
        .options(selectinload(Registration.user))
        .order_by(User.full_name)
    ).all()
    return [
        {
            "registration_id": registration.id,
            "user_id": registration.user.id,
            "full_name": registration.user.full_name,
            "employee_code": registration.user.employee_code,
            "avatar_url": registration.user.avatar_url,
            "seat_id": seats.get(registration.id, (None, None, None))[0],
            "table_code": seats.get(registration.id, (None, None, None))[1],
            "seat_number": seats.get(registration.id, (None, None, None))[2],
        }
        for registration in registrations
    ]


def unseated_participants(db: Session, *, event: Event, viewer: User) -> list[dict[str, Any]]:
    """Mọi người tham gia chưa được xếp vào ghế cụ thể. Chỉ BTC xem được (có tên người).

    Đây đúng là con số `unseated` đang chặn kỳ chuyển sang `event_started`, nên dọn hết danh sách
    này là bắt đầu sự kiện được. Người chưa thuộc team nào luôn nằm ở đây: không team nào bốc thăm
    hộ họ nên không ai chọn ghế cho họ, BTC phải xếp tay.
    """
    if viewer.role not in ADMIN_ROLES:
        raise PermissionDeniedError("Chỉ Ban tổ chức xem được danh sách người chưa có ghế.")

    layout = find_layout(db, event.id)
    seated = (
        select(GalaSeatAssignment.registration_id).where(
            GalaSeatAssignment.seat_id.in_(_seat_ids(layout.id)),
            GalaSeatAssignment.registration_id.is_not(None),
        )
        if layout is not None
        else None
    )
    query = (
        select(Registration)
        .join(User, User.id == Registration.user_id)
        .outerjoin(Team, Team.id == User.team_id)
        .where(Registration.id.in_(_participant_ids(event.id)))
        .options(selectinload(Registration.user))
        # Người chưa có team lên đầu: họ là nhóm duy nhất không ai xếp hộ được.
        .order_by(User.team_id.is_not(None), Team.name, User.full_name)
    )
    if seated is not None:
        query = query.where(Registration.id.not_in(seated))

    teams = {team.id: team.name for team in db.scalars(select(Team))}
    return [
        {
            "registration_id": registration.id,
            "user_id": registration.user.id,
            "full_name": registration.user.full_name,
            "employee_code": registration.user.employee_code,
            "avatar_url": registration.user.avatar_url,
            "team_id": registration.user.team_id,
            "team_name": teams.get(registration.user.team_id),
        }
        for registration in db.scalars(query)
    ]


def assign_member(
    db: Session,
    *,
    event: Event,
    actor: User,
    seat_id: int,
    registration_id: int | None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    event_id, actor_id, actor_role = event.id, actor.id, actor.role
    with immediate_transaction(db):
        layout = get_layout(db, event_id)
        seat = _seat_in_layout(db, layout.id, seat_id)
        assignment = seat.assignment
        if assignment is None:
            # BTC xếp thẳng người vào ghế còn trống: ghế nhận luôn team của người đó, hoặc không
            # thuộc team nào nếu họ chưa có team. Trưởng nhóm thì vẫn phải chốt ghế trước.
            if actor_role not in ADMIN_ROLES or registration_id is None:
                raise ConflictError("Ghế này chưa thuộc team nào.", code="SEAT_NOT_CONFIRMED")
            assignment = _claim_free_seat(db, seat, registration_id, actor_id=actor_id)
        if actor_role not in ADMIN_ROLES:
            _ensure_not_cancelled(db, event_id=event_id, user_id=actor_id)
            team = led_team(db, actor_id)
            if team is None or team.id != assignment.team_id:
                raise PermissionDeniedError("Bạn chỉ gán người vào ghế của team mình.")

        before = assignment.registration_id
        previous_seat_id = _place_member(
            db, event_id, assignment, registration_id, enforce_team=actor_role not in ADMIN_ROLES
        )
        audit_service.log(
            db,
            action="gala.member_assigned",
            entity_type="gala_seat",
            entity_id=seat.id,
            actor_id=actor_id,
            event_id=event_id,
            before={"registration_id": before},
            after={"registration_id": registration_id, "previous_seat_id": previous_seat_id},
            ip_address=ip_address,
        )
        result = {"seat_id": seat.id, "registration_id": registration_id, "previous_seat_id": previous_seat_id}
    return result


def _claim_free_seat(
    db: Session, seat: GalaSeat, registration_id: int, *, actor_id: int
) -> GalaSeatAssignment:
    """Cho một ghế còn trống thuộc về team của người sắp ngồi (NULL nếu họ chưa có team)."""
    if not seat.is_available or not seat.table.is_available:
        raise ConflictError(
            f"{_label(seat)} đang bị khoá. Mở khoá ghế trước khi xếp người.", code="SEAT_UNAVAILABLE"
        )
    # Chỉ hold CÒN HẠN mới chặn: hold quá hạn được dọn lazy lúc đọc sơ đồ, không có lý do bắt BTC
    # chờ tới nhịp đọc kế tiếp mới xếp được ghế.
    if seat.hold is not None and seat.hold.expires_at > utcnow_iso():
        raise ConflictError(
            f"{_label(seat)} đang được một team giữ. Chờ hết hạn giữ hoặc chọn ghế khác.",
            code="SEAT_HELD",
        )
    seat.hold = None
    team_id = db.scalar(
        select(User.team_id).join(Registration, Registration.user_id == User.id).where(
            Registration.id == registration_id
        )
    )
    seat.assignment = GalaSeatAssignment(
        team_id=team_id, confirmed_by=actor_id, confirmed_at=utcnow_iso()
    )
    db.flush()
    return seat.assignment


def _place_member(
    db: Session,
    event_id: int,
    assignment: GalaSeatAssignment,
    registration_id: int | None,
    *,
    enforce_team: bool = True,
) -> int | None:
    """Đặt người vào ghế; nếu họ đang ngồi ghế khác thì chuyển (UNIQUE registration_id).

    Trưởng nhóm chỉ xếp người trong team. BTC (`enforce_team=False`) xếp được cả người chưa thuộc
    team nào — không thì những người đó không bao giờ có ghế và kỳ không bắt đầu được.
    """
    if registration_id is None:
        assignment.registration_id = None
        if assignment.team_id is None:
            # Ghế không thuộc team nào mà cũng không còn ai ngồi thì không còn lý do tồn tại —
            # giữ lại là một ghế "đã có chủ" mà chủ là không ai, không ai chọn được nữa.
            db.delete(assignment)
        db.flush()
        return None

    registration = db.scalar(
        select(Registration)
        .where(
            Registration.id == registration_id,
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
        )
        .options(selectinload(Registration.user))
    )
    if registration is None:
        raise NotFoundError(
            f"Không tìm thấy người tham gia #{registration_id} trong kỳ này.", code="REGISTRATION_NOT_FOUND"
        )
    if enforce_team and registration.user.team_id != assignment.team_id:
        raise AppError(
            f"{registration.user.full_name} không thuộc team sở hữu ghế này.", code="MEMBER_NOT_IN_TEAM"
        )

    previous = db.scalar(
        select(GalaSeatAssignment).where(
            GalaSeatAssignment.registration_id == registration_id, GalaSeatAssignment.id != assignment.id
        )
    )
    previous_seat_id = None
    if previous is not None:
        previous_seat_id = previous.seat_id
        previous.registration_id = None
        db.flush()
    assignment.registration_id = registration_id
    return previous_seat_id


# --- BTC: ép gán / gỡ / khoá ghế ---


def admin_update_seat(
    db: Session,
    *,
    event: Event,
    actor: User,
    seat_id: int,
    data: dict[str, Any],
    reason: str,
    ip_address: str | None = None,
) -> None:
    event_id, actor_id = event.id, actor.id
    try:
        with immediate_transaction(db):
            layout = get_layout(db, event_id)
            seat = _seat_in_layout(db, layout.id, seat_id)
            before = _seat_snapshot(seat)
            now = utcnow_iso()

            if "team_id" in data:
                team_id = data["team_id"]
                seat.hold = None
                if team_id is None:
                    seat.assignment = None
                else:
                    team = db.get(Team, team_id)
                    if team is None or not team.is_active:
                        raise NotFoundError(f"Không tìm thấy team #{team_id}.", code="TEAM_NOT_FOUND")
                    if seat.assignment is None:
                        if not seat.is_available or not seat.table.is_available:
                            raise ConflictError(
                                f"{_label(seat)} đang bị khoá. Mở khoá ghế trước khi gán team.",
                                code="SEAT_UNAVAILABLE",
                            )
                        seat.assignment = GalaSeatAssignment(
                            team_id=team_id, confirmed_by=actor_id, confirmed_at=now
                        )
                    elif seat.assignment.team_id != team_id:
                        seat.assignment.team_id = team_id
                        seat.assignment.registration_id = None
                        seat.assignment.confirmed_by = actor_id
                        seat.assignment.confirmed_at = now
                db.flush()

            if "registration_id" in data:
                if seat.assignment is None:
                    raise ConflictError(
                        "Ghế chưa thuộc team nào — gán team trước khi gán người.", code="SEAT_NOT_CONFIRMED"
                    )
                _place_member(db, event_id, seat.assignment, data["registration_id"], enforce_team=False)

            if "is_available" in data:
                if data["is_available"] is False:
                    if seat.assignment is not None:
                        raise ConflictError(
                            f"{_label(seat)} đang thuộc team. Gỡ team khỏi ghế trước khi khoá.", code="SEAT_TAKEN"
                        )
                    seat.hold = None
                seat.is_available = bool(data["is_available"])
            db.flush()

            after = _seat_snapshot(seat)
            audit_service.log(
                db,
                action="gala.seat_updated",
                entity_type="gala_seat",
                entity_id=seat.id,
                actor_id=actor_id,
                event_id=event_id,
                before=before,
                after=after,
                reason=reason,
                ip_address=ip_address,
            )
    except IntegrityError as exc:
        raise ConflictError("Ghế hoặc người này vừa được gán ở chỗ khác. Tải lại sơ đồ.", code="SEAT_TAKEN") from exc


def _seat_snapshot(seat: GalaSeat) -> dict[str, Any]:
    return {
        "is_available": seat.is_available,
        "team_id": seat.assignment.team_id if seat.assignment else None,
        "registration_id": seat.assignment.registration_id if seat.assignment else None,
    }


def _ensure_published(event_status: str) -> None:
    if not EventStatus(event_status).at_least(EventStatus.INFORMATION_PUBLISHED):
        raise InvalidEventStatusError(
            "Công bố thông tin phân bổ trước khi mở chọn ghế Gala.",
            code="NOT_PUBLISHED",
            details={"current_status": event_status},
        )


def _confirmed_by_team(db: Session, layout_id: int) -> dict[int, int]:
    return dict(
        db.execute(
            select(GalaSeatAssignment.team_id, func.count(GalaSeatAssignment.id))
            .where(GalaSeatAssignment.seat_id.in_(_seat_ids(layout_id)))
            .group_by(GalaSeatAssignment.team_id)
        ).all()
    )


def _participant_ids(event_id: int):
    return select(Registration.id).where(
        Registration.event_id == event_id,
        Registration.status == RegistrationStatus.SUBMITTED,
        Registration.is_participating.is_(True),
    )


# --- BTC: mở lại chọn ghế ---


def reopen(
    db: Session, *, event: Event, actor: User, jobs: list[dict[str, Any]], ip_address: str | None = None
) -> None:
    """Mở lại chọn ghế sau khi đã kết thúc (BTC bấm kết thúc sớm, có người đăng ký muộn...).

    Team chưa đủ ghế chọn lại theo ĐÚNG thứ tự đã bốc thăm; team đủ ghế giữ nguyên, không mất ghế.
    Quota tính lại theo số người tham gia hiện tại; team mới có người tham gia xếp cuối hàng.
    """
    event_id, event_status, actor_id = event.id, event.status, actor.id
    with immediate_transaction(db):
        layout = get_layout(db, event_id)
        if layout.selection_status != GalaSelectionStatus.FINALIZED:
            raise ConflictError(
                "Chỉ mở lại được khi việc chọn ghế đã kết thúc.",
                code="GALA_NOT_FINALIZED",
                details={"selection_status": layout.selection_status},
            )
        _ensure_published(event_status)

        quotas = _team_quotas(db, event_id)
        confirmed = _confirmed_by_team(db, layout.id)
        orders = list(
            db.scalars(
                select(GalaDrawOrder).where(GalaDrawOrder.layout_id == layout.id).order_by(GalaDrawOrder.draw_position)
            )
        )
        known = {order.team_id for order in orders}
        position = max((order.draw_position for order in orders), default=0)
        added: list[int] = []
        for team_id in sorted(set(quotas) - known):
            position += 1
            order = GalaDrawOrder(
                layout_id=layout.id, team_id=team_id, draw_position=position, quota=quotas[team_id],
                status=DrawStatus.WAITING,
            )
            db.add(order)
            orders.append(order)
            added.append(team_id)

        pending: list[GalaDrawOrder] = []
        for order in orders:
            seats = confirmed.get(order.team_id, 0)
            order.quota = max(quotas.get(order.team_id, 0), seats)
            if seats < order.quota:
                order.status = DrawStatus.WAITING
                order.turn_started_at = None
                order.turn_ends_at = None
                pending.append(order)
        if not pending:
            raise ConflictError("Mọi team đã đủ ghế — không cần mở lại.", code="GALA_NOTHING_TO_REOPEN")

        db.flush()
        layout.selection_status = GalaSelectionStatus.OPEN
        _start_turn(db, layout, pending[0], jobs)
        audit_service.log(
            db,
            action="gala.selection_reopened",
            entity_type="gala_layout",
            entity_id=layout.id,
            actor_id=actor_id,
            event_id=event_id,
            after={
                "team_ids": [order.team_id for order in pending],
                "added_team_ids": added,
                "first_team_id": pending[0].team_id,
            },
            ip_address=ip_address,
        )


def seating_gaps(db: Session, *, event_id: int) -> dict[str, Any] | None:
    """Chỗ ngồi Gala còn thiếu gì. None = kỳ không có sơ đồ Gala.

    Dùng để chặn chuyển kỳ sang `event_started` và hiện trên dashboard.
    """
    layout = find_layout(db, event_id)
    if layout is None:
        return None
    layout_id, selection_status = layout.id, layout.selection_status
    quotas = _team_quotas(db, event_id)
    confirmed = _confirmed_by_team(db, layout_id)
    names = dict(db.execute(select(Team.id, Team.name).where(Team.id.in_(list(quotas)))).all()) if quotas else {}
    teams_missing = sorted(
        (
            {
                "team_id": team_id,
                "team_name": names.get(team_id, f"Team #{team_id}"),
                "participants": count,
                "seats": confirmed.get(team_id, 0),
            }
            for team_id, count in quotas.items()
            if confirmed.get(team_id, 0) < count
        ),
        key=lambda item: item["team_name"],
    )
    participant_ids = _participant_ids(event_id)
    participants = db.scalar(select(func.count()).select_from(participant_ids.subquery())) or 0
    seated = db.scalar(
        select(func.count(GalaSeatAssignment.id)).where(
            GalaSeatAssignment.seat_id.in_(_seat_ids(layout_id)),
            GalaSeatAssignment.registration_id.in_(participant_ids),
        )
    ) or 0
    return {
        "selection_status": selection_status,
        "teams_missing": teams_missing,
        "participants": participants,
        "seated": seated,
        "unseated": participants - seated,
    }


# --- Xếp thành viên ngẫu nhiên ---


def auto_assign_members(
    db: Session,
    *,
    event: Event,
    actor: User,
    team_id: int | None = None,
    reshuffle: bool = False,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Xếp ngẫu nhiên thành viên vào các ghế team đã chốt.

    Mặc định chỉ xếp người CHƯA có ghế vào ghế còn trống — không đụng chỗ đã đổi tay. `reshuffle`
    xáo lại cả team. Người không còn tham gia mà vẫn chiếm ghế thì được gỡ ra trước.
    """
    event_id, actor_id, actor_role = event.id, actor.id, actor.role
    with immediate_transaction(db):
        layout = get_layout(db, event_id)
        target = _seating_team_id(
            db, event_id=event_id, actor_id=actor_id, actor_role=actor_role, team_id=team_id
        )
        seats = list(
            db.scalars(
                select(GalaSeatAssignment)
                .join(GalaSeat, GalaSeat.id == GalaSeatAssignment.seat_id)
                .join(GalaTable, GalaTable.id == GalaSeat.table_id)
                .where(GalaTable.layout_id == layout.id, GalaSeatAssignment.team_id == target)
                .order_by(GalaTable.pos_y, GalaTable.pos_x, GalaTable.table_code, GalaSeat.seat_number)
            )
        )
        if not seats:
            raise ConflictError("Team chưa chốt ghế nào để xếp thành viên.", code="NO_TEAM_SEATS")

        members = list(
            db.scalars(
                select(Registration.id)
                .join(User, User.id == Registration.user_id)
                .where(Registration.id.in_(_participant_ids(event_id)), User.team_id == target)
                .order_by(Registration.id)
            )
        )
        member_ids = set(members)
        for assignment in seats:
            if assignment.registration_id is not None and (reshuffle or assignment.registration_id not in member_ids):
                assignment.registration_id = None
        db.flush()

        seated = (
            set(db.scalars(select(GalaSeatAssignment.registration_id).where(GalaSeatAssignment.registration_id.in_(members))))
            if members
            else set()
        )
        waiting = [registration_id for registration_id in members if registration_id not in seated]
        random.SystemRandom().shuffle(waiting)
        free = [assignment for assignment in seats if assignment.registration_id is None]
        pairs = list(zip(free, waiting, strict=False))
        for assignment, registration_id in pairs:
            assignment.registration_id = registration_id
        db.flush()

        result = {
            "team_id": target,
            "placed": len(pairs),
            "unseated": len(waiting) - len(pairs),
            "free_seats": len(free) - len(pairs),
            "reshuffle": reshuffle,
        }
        audit_service.log(
            db,
            action="gala.members_auto_assigned",
            entity_type="gala_layout",
            entity_id=layout.id,
            actor_id=actor_id,
            event_id=event_id,
            after=result,
            ip_address=ip_address,
        )
    return result


def _seating_team_id(
    db: Session, *, event_id: int, actor_id: int, actor_role: str, team_id: int | None
) -> int:
    if actor_role in ADMIN_ROLES:
        if team_id is None:
            raise AppError("Chọn team cần xếp chỗ.", code="TEAM_REQUIRED")
        if db.get(Team, team_id) is None:
            raise NotFoundError(f"Không tìm thấy team #{team_id}.", code="TEAM_NOT_FOUND")
        return team_id
    _ensure_not_cancelled(db, event_id=event_id, user_id=actor_id)
    team = led_team(db, actor_id)
    if team is None or (team_id is not None and team_id != team.id):
        raise PermissionDeniedError("Bạn chỉ xếp chỗ cho thành viên team mình.")
    return team.id


# --- Lượt của tôi (banner nhắc Trưởng nhóm) ---


def my_turn(db: Session, *, event: Event, user: User, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    event_id, user_id = event.id, user.id
    team = led_team(db, user_id)
    layout = find_layout(db, event_id)
    result: dict[str, Any] = {
        "configured": layout is not None,
        "is_leader": team is not None,
        "selection_status": layout.selection_status if layout else None,
        "team_id": team.id if team else None,
        "team_name": team.name if team else None,
        "draw_position": None,
        "status": None,
        "is_my_turn": False,
        "turn_ends_at": None,
        "teams_ahead": None,
        "active_team_name": None,
        "quota": 0,
        "confirmed": 0,
        "remaining": 0,
        "server_time": utcnow_iso(),
    }
    if team is None or layout is None:
        return result

    team_id, layout_id = team.id, layout.id
    refresh(db, layout_id=layout_id, jobs=jobs)
    layout = db.get(GalaLayout, layout_id)
    draw = _draw_state(db, layout)
    mine = next((order for order in draw["orders"] if order["team_id"] == team_id), None)
    active = next((order for order in draw["orders"] if order["status"] == DrawStatus.ACTIVE), None)
    result.update(
        selection_status=layout.selection_status,
        active_team_name=active["team_name"] if active else None,
        server_time=draw["server_time"],
    )
    if mine is None:
        return result

    is_turn = layout.selection_status == GalaSelectionStatus.OPEN and active is not None and active["team_id"] == team_id
    ahead = (
        sum(
            1
            for order in draw["orders"]
            if order["position"] < mine["position"] and order["status"] in (DrawStatus.ACTIVE, DrawStatus.WAITING)
        )
        if mine["status"] == DrawStatus.WAITING
        else 0
    )
    result.update(
        draw_position=mine["position"],
        status=mine["status"],
        is_my_turn=is_turn,
        turn_ends_at=mine["turn_ends_at"] if is_turn else None,
        teams_ahead=ahead,
        quota=mine["quota"],
        confirmed=mine["confirmed"],
        remaining=mine["remaining"],
    )
    return result
