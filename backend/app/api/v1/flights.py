"""Endpoint quản lý chuyến bay (Module 2, docs/04-api-spec.md §5).

Toàn bộ router dành cho BTC. CBNV thấy chuyến bay của mình qua My Journey, và chỉ khi
BTC đã công bố — không qua đây.

Phân bổ tự động (`POST /flights/allocate`) là bước 12-13, chưa có ở đây.
"""

from fastapi import APIRouter, Depends, Query, Request, status

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
from app.services import flight_service

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
