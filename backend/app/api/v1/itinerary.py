"""Lịch trình chương trình: BTC quản lý, CBNV đọc bản đã lọc qua `/journey/me`.

Chỉ BTC được thấy/sửa danh sách thô (gồm cả mốc riêng theo ca/team) — CBNV thấy bản
lọc theo ca được xếp của mình trong My Journey, không bao giờ thấy lịch của ca khác.
"""

from fastapi import APIRouter, Request, status

from app.core.dependencies import ActiveEvent, AdminUser, DbSession, get_client_ip
from app.schemas.itinerary import (
    ItineraryIn,
    ItineraryOut,
    ItineraryReorder,
    ItineraryUpdate,
)
from app.services import audit_service, itinerary_service

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


def _audit(db, request, actor, action, entity_id, before=None, after=None) -> None:
    audit_service.log(
        db,
        action=action,
        entity_type="itinerary",
        entity_id=entity_id,
        actor_id=actor.id,
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    db.commit()


def _to_out(item) -> ItineraryOut:
    """Kèm tên chặng để màn hình BTC hiện "Chỉ người đi xe: HN → Sân bay" mà không phải
    tự tra bảng chặng."""
    return ItineraryOut(
        **{
            **ItineraryOut.model_validate(item).model_dump(),
            "trip_leg_name": item.trip_leg.name if item.trip_leg else None,
        }
    )


@router.get("", response_model=list[ItineraryOut], summary="Toàn bộ mốc lịch trình của kỳ")
def list_itinerary(event: ActiveEvent, db: DbSession, _: AdminUser) -> list[ItineraryOut]:
    return [_to_out(item) for item in itinerary_service.list_items(db, event)]


@router.post(
    "", response_model=ItineraryOut, status_code=status.HTTP_201_CREATED, summary="Thêm mốc lịch trình"
)
def create_itinerary(
    payload: ItineraryIn, event: ActiveEvent, actor: AdminUser, db: DbSession, request: Request
) -> ItineraryOut:
    item = itinerary_service.create_item(db, event, payload.model_dump())
    _audit(db, request, actor, "itinerary.created", item.id, after=payload.model_dump())
    return _to_out(item)


@router.patch("/{item_id}", response_model=ItineraryOut, summary="Sửa mốc lịch trình")
def update_itinerary(
    item_id: int,
    payload: ItineraryUpdate,
    event: ActiveEvent,
    actor: AdminUser,
    db: DbSession,
    request: Request,
) -> ItineraryOut:
    changes = payload.model_dump(exclude_unset=True)
    item = itinerary_service.update_item(db, event, item_id, changes)
    _audit(db, request, actor, "itinerary.updated", item_id, after=changes)
    return _to_out(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá mốc lịch trình")
def delete_itinerary(
    item_id: int, event: ActiveEvent, actor: AdminUser, db: DbSession, request: Request
) -> None:
    item = itinerary_service.delete_item(db, event, item_id)
    _audit(
        db,
        request,
        actor,
        "itinerary.deleted",
        item_id,
        before={"day_date": item.day_date, "title": item.title},
    )


@router.post("/reorder", response_model=list[ItineraryOut], summary="Xếp lại thứ tự mốc trong ngày")
def reorder_itinerary(
    payload: ItineraryReorder,
    event: ActiveEvent,
    actor: AdminUser,
    db: DbSession,
    request: Request,
) -> list[ItineraryOut]:
    rows = itinerary_service.reorder_day(db, event, payload.day_date, payload.ordered_ids)
    _audit(
        db,
        request,
        actor,
        "itinerary.reordered",
        0,
        after={"day_date": payload.day_date, "ordered_ids": payload.ordered_ids},
    )
    return [_to_out(item) for item in rows]
