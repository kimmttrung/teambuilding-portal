"""Endpoint quản lý xe, Trưởng xe và phân xe (Module 3, docs/04-api-spec.md §7).

Phần lớn dành cho BTC. Riêng danh sách hành khách mở cho Trưởng xe của CHÍNH xe đó
(vai trò 🔵) — kiểm tra ở service, không phải chặn cả router theo role.

`/buses/export` xuất Excel theo từng chặng (bước 21).
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response, status

from app.api.v1.downloads import xlsx_response
from app.api.v1.email_jobs import JourneyTracker, send_journey_notices
from app.core.dependencies import (
    ActiveEvent,
    AdminUser,
    CurrentUser,
    DbSession,
    Notify,
    get_client_ip,
    require_admin,
)
from app.models.transportation import Bus
from app.schemas.bus import (
    BusAllocateRequest,
    BusAllocationResponse,
    BusIn,
    BusOut,
    BusPassengerOut,
    BusUpdate,
    LeaderUpdate,
)
from app.services import bus_service, export_service, transport_timing_service
from app.services.allocator.bus_types import BusAllocationResult

router = APIRouter(prefix="/buses", tags=["buses"])


@router.get(
    "",
    response_model=list[BusOut],
    dependencies=[Depends(require_admin)],
    summary="Danh sách xe + ghế trống",
)
def list_buses(
    event: ActiveEvent,
    db: DbSession,
    trip_leg_id: int | None = None,
    q: str | None = Query(default=None, description="Tìm theo mã xe, biển số, Trưởng xe"),
) -> list[BusOut]:
    rows = bus_service.list_buses(db, event_id=event.id, trip_leg_id=trip_leg_id, search=q)
    issues = transport_timing_service.bus_timing_issues(db, event_id=event.id)
    return [_to_schema(bus, assigned, issues.get(bus.id, [])) for bus, assigned in rows]


@router.get(
    "/export",
    dependencies=[Depends(require_admin)],
    summary="Xuất danh sách xe + hành khách theo từng chặng (.xlsx)",
)
def export_buses(event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request) -> Response:
    content, filename = export_service.export_buses(
        db, event=event, actor=actor, ip_address=get_client_ip(request)
    )
    return xlsx_response(content, filename)


@router.post(
    "/allocate",
    response_model=BusAllocationResponse,
    summary="Phân xe tự động cho một chặng (dry-run hoặc ghi thật)",
)
def allocate(
    background_tasks: BackgroundTasks,
    payload: BusAllocateRequest,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    notify: Notify = False,
) -> BusAllocationResponse:
    """Chạy SAU phân bổ chuyến bay: chặng gắn sân bay cần biết mỗi người bay chuyến nào."""
    tracker = JourneyTracker(db, event, notify=notify and not payload.dry_run)
    if payload.dry_run:
        result, leg = bus_service.preview(
            db,
            event=event,
            trip_leg_id=payload.trip_leg_id,
            force_reallocate=payload.force_reallocate,
        )
        send_journey_notices(background_tasks, tracker, actor, request, "bus.allocated")
        return _to_allocation_schema(result, leg.code, dry_run=True, removed_stale=0)

    result, leg_code, removed_stale = bus_service.commit(
        db,
        event=event,
        trip_leg_id=payload.trip_leg_id,
        actor=actor,
        force_reallocate=payload.force_reallocate,
        ip_address=get_client_ip(request),
    )
    send_journey_notices(background_tasks, tracker, actor, request, "bus.allocated")
    return _to_allocation_schema(result, leg_code, dry_run=False, removed_stale=removed_stale)


@router.post("", response_model=BusOut, status_code=status.HTTP_201_CREATED, summary="Thêm xe")
def create_bus(
    payload: BusIn,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
) -> BusOut:
    bus = bus_service.create_bus(
        db,
        event=event,
        data=payload.model_dump(),
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return _to_schema(bus, 0)


@router.get(
    "/{bus_id}",
    response_model=BusOut,
    dependencies=[Depends(require_admin)],
    summary="Chi tiết một xe",
)
def get_bus(bus_id: int, event: ActiveEvent, db: DbSession) -> BusOut:
    bus = bus_service.get_bus(db, event_id=event.id, bus_id=bus_id)
    return _to_schema(bus, bus_service.count_assigned(db, bus.id))


@router.patch("/{bus_id}", response_model=BusOut, summary="Sửa xe")
def update_bus(
    background_tasks: BackgroundTasks,
    bus_id: int,
    payload: BusUpdate,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    notify: Notify = False,
) -> BusOut:
    tracker = JourneyTracker(db, event, notify=notify)
    bus = bus_service.get_bus(db, event_id=event.id, bus_id=bus_id)
    updated = bus_service.update_bus(
        db,
        event=event,
        bus=bus,
        data=payload.model_dump(exclude_unset=True),
        actor=actor,
        ip_address=get_client_ip(request),
    )
    send_journey_notices(background_tasks, tracker, actor, request, "bus.updated")
    return _to_schema(updated, bus_service.count_assigned(db, updated.id))


@router.delete("/{bus_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá xe")
def delete_bus(
    background_tasks: BackgroundTasks,
    bus_id: int,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    notify: Notify = False,
) -> None:
    tracker = JourneyTracker(db, event, notify=notify)
    bus = bus_service.get_bus(db, event_id=event.id, bus_id=bus_id)
    bus_service.delete_bus(db, event=event, bus=bus, actor=actor, ip_address=get_client_ip(request))
    send_journey_notices(background_tasks, tracker, actor, request, "bus.deleted")


@router.patch("/{bus_id}/leader", response_model=BusOut, summary="Gán Trưởng xe")
def set_leader(
    background_tasks: BackgroundTasks,
    bus_id: int,
    payload: LeaderUpdate,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    notify: Notify = False,
) -> BusOut:
    tracker = JourneyTracker(db, event, notify=notify)
    bus = bus_service.get_bus(db, event_id=event.id, bus_id=bus_id)
    updated = bus_service.set_leader(
        db,
        event=event,
        bus=bus,
        data=payload.model_dump(),
        actor=actor,
        ip_address=get_client_ip(request),
    )
    send_journey_notices(background_tasks, tracker, actor, request, "bus.leader_changed")
    return _to_schema(updated, bus_service.count_assigned(db, updated.id))


@router.get(
    "/{bus_id}/passengers",
    response_model=list[BusPassengerOut],
    summary="Hành khách của một xe (BTC hoặc Trưởng xe của xe này)",
)
def list_passengers(
    bus_id: int, event: ActiveEvent, db: DbSession, user: CurrentUser
) -> list[BusPassengerOut]:
    bus = bus_service.get_bus(db, event_id=event.id, bus_id=bus_id)
    bus_service.ensure_can_view_passengers(user, bus)
    return [BusPassengerOut(**row) for row in bus_service.list_passengers(db, bus=bus)]


# --- Chuyển đổi sang schema ---


def _to_schema(bus: Bus, assigned: int, timing_issues: list[str] | None = None) -> BusOut:
    leg = bus.trip_leg
    # Dựng lại qua constructor, KHÔNG dùng `model_copy(update=...)`: model_copy bỏ qua
    # validate, nên chuỗi 'outbound' không được đổi sang enum `FlightDirection` và Pydantic
    # cảnh báo "Expected enum" mỗi lần serialize response.
    return BusOut(
        **{
            **BusOut.model_validate(bus).model_dump(),
            "trip_leg_code": leg.code if leg else "",
            "trip_leg_name": leg.name if leg else "",
            "direction": leg.direction if leg else None,
            "airport_linked": bool(leg and leg.is_airport_linked),
            "assigned_count": assigned,
            "remaining_seats": bus.capacity - assigned,
            "load_ratio": round(assigned / bus.capacity, 4) if bus.capacity else 0.0,
            "pickup_point_name": bus.pickup_point.name if bus.pickup_point else None,
            "linked_flight_code": bus.linked_flight.flight_code if bus.linked_flight else None,
            "timing_issues": timing_issues or [],
        }
    )


def _to_allocation_schema(
    result: BusAllocationResult, leg_code: str, *, dry_run: bool, removed_stale: int
) -> BusAllocationResponse:
    return BusAllocationResponse(
        trip_leg_id=result.trip_leg_id,
        trip_leg_code=leg_code,
        airport_linked=result.airport_linked,
        dry_run=dry_run,
        committed=not dry_run,
        summary=result.summary.__dict__,
        buses=[
            {**load.__dict__, "teams": [team.__dict__ for team in load.teams]}
            for load in result.buses
        ],
        flags=[flag.__dict__ for flag in result.flags],
        removed_stale=removed_stale,
    )
