"""Endpoint quản lý chuyến bay và chạy phân bổ (Module 2, docs/04-api-spec.md §5).

Toàn bộ router dành cho BTC. CBNV thấy chuyến bay của mình qua My Journey, và chỉ khi
BTC đã công bố — không qua đây.
"""

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.v1.downloads import xlsx_response
from app.core.dependencies import (
    ActiveEvent,
    AdminUser,
    DbSession,
    get_client_ip,
    require_admin,
)
from app.models.enums import FlightDirection
from app.models.flight import Flight
from app.schemas.flight import (
    FlightCapacitySummary,
    FlightIn,
    FlightOut,
    FlightUpdate,
    PassengerOut,
)
from app.schemas.flight_allocation import AllocateRequest, AllocationResponse
from app.services import export_service, flight_allocation_service, flight_service
from app.services.allocator import AllocationResult

router = APIRouter(
    prefix="/flights", tags=["flights"], dependencies=[Depends(require_admin)]
)


@router.get("", response_model=list[FlightOut], summary="Danh sách chuyến bay + slot")
def list_flights(
    event: ActiveEvent,
    db: DbSession,
    direction: FlightDirection | None = None,
    shift_id: int | None = None,
    is_active: bool | None = None,
    q: str | None = Query(default=None, description="Tìm theo mã chuyến hoặc mã sân bay"),
) -> list[FlightOut]:
    rows = flight_service.list_flights(
        db,
        event_id=event.id,
        direction=direction.value if direction else None,
        shift_id=shift_id,
        is_active=is_active,
        search=q,
    )
    return [_to_schema(flight, assigned) for flight, assigned in rows]


@router.get(
    "/summary",
    response_model=FlightCapacitySummary,
    summary="Tổng quan slot theo chiều và theo ca",
)
def get_capacity_summary(event: ActiveEvent, db: DbSession) -> FlightCapacitySummary:
    return FlightCapacitySummary(**flight_service.capacity_summary(db, event_id=event.id))


@router.get("/export", summary="Xuất danh sách hành khách để đặt vé (.xlsx, có CCCD)")
def export_manifest(event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request) -> Response:
    """File có ngày sinh + số giấy tờ: mỗi lần tải đều ghi nhật ký là file nhạy cảm."""
    content, filename = export_service.export_flight_manifest(
        db, event=event, actor=actor, ip_address=get_client_ip(request)
    )
    return xlsx_response(content, filename)


@router.post(
    "/allocate",
    response_model=AllocationResponse,
    summary="Chạy phân bổ tự động (dry-run hoặc ghi thật)",
)
def allocate(
    payload: AllocateRequest,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
) -> AllocationResponse:
    """`dry_run=true` chỉ trả preview; `dry_run=false` ghi vào DB trong một transaction.

    Ghi thật đòi kỳ đã đóng đăng ký — xem trước thì lúc nào cũng được.
    """
    direction = payload.direction.value
    removed_stale = 0

    if payload.dry_run:
        result = flight_allocation_service.preview(
            db,
            event=event,
            direction=direction,
            force_reallocate=payload.force_reallocate,
            seed=payload.seed,
        )
    else:
        result, removed_stale = flight_allocation_service.commit(
            db,
            event=event,
            direction=direction,
            actor=actor,
            force_reallocate=payload.force_reallocate,
            seed=payload.seed,
            ip_address=get_client_ip(request),
        )

    return _to_allocation_schema(result, dry_run=payload.dry_run, removed_stale=removed_stale)


@router.post(
    "",
    response_model=FlightOut,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm chuyến bay",
)
def create_flight(
    payload: FlightIn,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
) -> FlightOut:
    flight = flight_service.create_flight(
        db,
        event=event,
        data=payload.model_dump(),
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return _to_schema(flight, 0)


@router.get("/{flight_id}", response_model=FlightOut, summary="Chi tiết một chuyến bay")
def get_flight(flight_id: int, event: ActiveEvent, db: DbSession) -> FlightOut:
    flight = flight_service.get_flight(db, event_id=event.id, flight_id=flight_id)
    return _to_schema(flight, flight_service.count_assigned(db, flight.id))


@router.patch("/{flight_id}", response_model=FlightOut, summary="Sửa chuyến bay")
def update_flight(
    flight_id: int,
    payload: FlightUpdate,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
) -> FlightOut:
    flight = flight_service.get_flight(db, event_id=event.id, flight_id=flight_id)
    updated = flight_service.update_flight(
        db,
        event=event,
        flight=flight,
        data=payload.model_dump(exclude_unset=True),
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return _to_schema(updated, flight_service.count_assigned(db, updated.id))


@router.delete(
    "/{flight_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá chuyến bay"
)
def delete_flight(
    flight_id: int,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
) -> None:
    flight = flight_service.get_flight(db, event_id=event.id, flight_id=flight_id)
    flight_service.delete_flight(
        db,
        event=event,
        flight=flight,
        actor=actor,
        ip_address=get_client_ip(request),
    )


@router.get(
    "/{flight_id}/passengers",
    response_model=list[PassengerOut],
    summary="Hành khách của một chuyến",
)
def list_passengers(flight_id: int, event: ActiveEvent, db: DbSession) -> list[PassengerOut]:
    flight = flight_service.get_flight(db, event_id=event.id, flight_id=flight_id)
    return [
        PassengerOut(**passenger)
        for passenger in flight_service.list_passengers(db, flight=flight)
    ]


# --- Chuyển đổi sang schema ---


def _to_allocation_schema(
    result: AllocationResult, *, dry_run: bool, removed_stale: int
) -> AllocationResponse:
    """Dataclass của thuật toán -> response JSON.

    Thuật toán không biết Pydantic (nó là hàm thuần), nên việc chuyển đổi nằm ở đây.
    """
    return AllocationResponse(
        direction=result.direction,
        dry_run=dry_run,
        committed=not dry_run,
        seed=result.seed,
        params=result.params,
        summary=result.summary.__dict__,
        flights=[
            {
                **load.__dict__,
                "teams": [team.__dict__ for team in load.teams],
            }
            for load in result.flights
        ],
        flags=[flag.__dict__ for flag in result.flags],
        removed_stale=removed_stale,
    )


def _to_schema(flight: Flight, assigned: int) -> FlightOut:
    """Gắn các số liệu slot suy ra — chúng là thuộc tính tính toán, không phải cột."""
    usable = flight.usable_capacity
    return FlightOut.model_validate(flight).model_copy(
        update={
            "shift_code": flight.shift.code if flight.shift else None,
            "shift_name": flight.shift.name if flight.shift else None,
            "usable_capacity": usable,
            "assigned_count": assigned,
            "remaining_slots": usable - assigned,
            "load_ratio": round(assigned / usable, 4) if usable else 0.0,
        }
    )
