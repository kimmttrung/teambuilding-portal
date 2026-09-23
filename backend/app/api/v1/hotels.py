"""Endpoint quản lý khách sạn (docs/04-api-spec.md §6). Chỉ BTC."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.api.v1.email_jobs import JourneyTracker, send_journey_notices
from app.core.dependencies import (
    ActiveEvent,
    AdminUser,
    DbSession,
    Notify,
    get_client_ip,
    require_admin,
)
from app.models.accommodation import Hotel
from app.schemas.accommodation import HotelIn, HotelOut, HotelUpdate
from app.services import accommodation_service

router = APIRouter(prefix="/hotels", tags=["hotels"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[HotelOut], summary="Danh sách khách sạn")
def list_hotels(event: ActiveEvent, db: DbSession) -> list[HotelOut]:
    return [
        _to_schema(hotel, rooms, beds, assigned)
        for hotel, rooms, beds, assigned in accommodation_service.list_hotels(db, event_id=event.id)
    ]


@router.post("", response_model=HotelOut, status_code=status.HTTP_201_CREATED, summary="Thêm khách sạn")
def create_hotel(
    payload: HotelIn, event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request
) -> HotelOut:
    hotel = accommodation_service.create_hotel(
        db, event=event, data=payload.model_dump(), actor=actor, ip_address=get_client_ip(request)
    )
    return _to_schema(hotel, 0, 0, 0)


@router.get("/{hotel_id}", response_model=HotelOut, summary="Chi tiết khách sạn")
def get_hotel(hotel_id: int, event: ActiveEvent, db: DbSession) -> HotelOut:
    hotel = accommodation_service.get_hotel(db, event_id=event.id, hotel_id=hotel_id)
    return _to_schema(hotel, *accommodation_service.hotel_stats(db, hotel.id))


@router.patch("/{hotel_id}", response_model=HotelOut, summary="Sửa khách sạn")
def update_hotel(
    background_tasks: BackgroundTasks,
    hotel_id: int,
    payload: HotelUpdate,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    notify: Notify = False,
) -> HotelOut:
    tracker = JourneyTracker(db, event, notify=notify)
    hotel = accommodation_service.get_hotel(db, event_id=event.id, hotel_id=hotel_id)
    updated = accommodation_service.update_hotel(
        db,
        event=event,
        hotel=hotel,
        data=payload.model_dump(exclude_unset=True),
        actor=actor,
        ip_address=get_client_ip(request),
    )
    send_journey_notices(background_tasks, tracker, actor, request, "hotel.updated")
    return _to_schema(updated, *accommodation_service.hotel_stats(db, updated.id))


@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá khách sạn")
def delete_hotel(
    background_tasks: BackgroundTasks,
    hotel_id: int, event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request,
    notify: Notify = False,
) -> None:
    tracker = JourneyTracker(db, event, notify=notify)
    hotel = accommodation_service.get_hotel(db, event_id=event.id, hotel_id=hotel_id)
    accommodation_service.delete_hotel(
        db, event=event, hotel=hotel, actor=actor, ip_address=get_client_ip(request)
    )
    send_journey_notices(background_tasks, tracker, actor, request, "hotel.deleted")


def _to_schema(hotel: Hotel, rooms: int, beds: int, assigned: int) -> HotelOut:
    return HotelOut(
        **{
            **HotelOut.model_validate(hotel).model_dump(),
            "room_count": rooms,
            "bed_count": beds,
            "assigned_count": assigned,
        }
    )
