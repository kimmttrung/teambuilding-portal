"""Endpoint quản lý phòng, tổng quan giường, import và xếp phòng tự động (docs/04-api-spec.md §6).

Chỉ BTC. `/rooms/export` có sheet đầu cùng cột với import, tải về sửa rồi import lại được.
"""

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status

from app.api.v1.downloads import xlsx_response
from app.core.dependencies import ActiveEvent, AdminUser, DbSession, get_client_ip, require_admin
from app.models.accommodation import Room
from app.models.enums import RoomGenderPolicy
from app.schemas.accommodation import (
    OccupantOut,
    RoomImportResult,
    RoomIn,
    RoomOut,
    RoomSummary,
    RoomUpdate,
)
from app.schemas.room_allocation import RoomAllocateRequest, RoomAllocationResponse
from app.services import (
    accommodation_service,
    export_service,
    room_allocation_service,
    room_import_service,
)
from app.services.allocator.room_types import RoomAllocationResult

router = APIRouter(prefix="/rooms", tags=["rooms"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[RoomOut], summary="Danh sách phòng + chỗ trống")
def list_rooms(
    event: ActiveEvent,
    db: DbSession,
    hotel_id: int | None = None,
    gender_policy: RoomGenderPolicy | None = None,
    available_only: bool = Query(default=False, description="Chỉ lấy phòng còn chỗ"),
    q: str | None = Query(default=None, description="Tìm theo số phòng"),
) -> list[RoomOut]:
    rows = accommodation_service.list_rooms(
        db,
        event_id=event.id,
        hotel_id=hotel_id,
        gender_policy=gender_policy.value if gender_policy else None,
        available_only=available_only,
        search=q,
    )
    return [_to_schema(room, occupied, captain) for room, occupied, captain in rows]


@router.get("/summary", response_model=RoomSummary, summary="Giường theo giới tính so với người tham gia")
def get_summary(event: ActiveEvent, db: DbSession) -> RoomSummary:
    return RoomSummary(**accommodation_service.summary(db, event_id=event.id))


@router.get("/export", summary="Xuất sơ đồ phân phòng (.xlsx, import lại được)")
def export_rooms(event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request) -> Response:
    content, filename = export_service.export_rooms(
        db, event=event, actor=actor, ip_address=get_client_ip(request)
    )
    return xlsx_response(content, filename)


@router.post(
    "/allocate",
    response_model=RoomAllocationResponse,
    summary="Xếp phòng tự động (dry-run hoặc ghi thật)",
)
def allocate(
    payload: RoomAllocateRequest,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
) -> RoomAllocationResponse:
    """Nam vào phòng nam, nữ vào phòng nữ; ưu tiên cùng team, cùng chuyến bay chiều đi, cùng phòng ban.

    Giữ nguyên người BTC đã xếp tay trừ khi `force_reallocate`. Ghi thật cần kỳ đã đóng đăng ký.
    """
    if payload.dry_run:
        result = room_allocation_service.preview(
            db, event=event, force_reallocate=payload.force_reallocate
        )
        return _to_allocation_schema(result, dry_run=True, removed_stale=0)

    result, removed_stale = room_allocation_service.commit(
        db,
        event=event,
        actor=actor,
        force_reallocate=payload.force_reallocate,
        ip_address=get_client_ip(request),
    )
    return _to_allocation_schema(result, dry_run=False, removed_stale=removed_stale)


@router.post("/import", response_model=RoomImportResult, summary="Import phân phòng từ Excel")
async def import_rooms(
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Query(default=True, description="true = chỉ kiểm tra, không ghi"),
    replace_existing: bool = Query(
        default=False, description="Cho phép chuyển người đang ở phòng khác sang phòng trong file"
    ),
) -> RoomImportResult:
    """Cột bắt buộc: 'Số phòng' + 'Mã NV' (hoặc 'Email'). Tuỳ chọn: 'Khách sạn', 'Trưởng phòng'.

    Còn lỗi thì không ghi dòng nào — trả về danh sách lỗi kèm số dòng Excel.
    """
    content = await file.read()
    result = room_import_service.import_room_assignments(
        db,
        event=event,
        content=content,
        actor=actor,
        dry_run=dry_run,
        replace_existing=replace_existing,
        ip_address=get_client_ip(request),
    )
    return RoomImportResult(**result)


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED, summary="Thêm phòng")
def create_room(
    payload: RoomIn, event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request
) -> RoomOut:
    room = accommodation_service.create_room(
        db, event=event, data=payload.model_dump(), actor=actor, ip_address=get_client_ip(request)
    )
    return _to_schema(room, 0, False)


@router.get("/{room_id}", response_model=RoomOut, summary="Chi tiết phòng")
def get_room(room_id: int, event: ActiveEvent, db: DbSession) -> RoomOut:
    room = accommodation_service.get_room(db, event_id=event.id, room_id=room_id)
    return _to_schema(room, *accommodation_service.room_occupancy(db, room.id))


@router.patch("/{room_id}", response_model=RoomOut, summary="Sửa phòng")
def update_room(
    room_id: int,
    payload: RoomUpdate,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
) -> RoomOut:
    room = accommodation_service.get_room(db, event_id=event.id, room_id=room_id)
    updated = accommodation_service.update_room(
        db,
        event=event,
        room=room,
        data=payload.model_dump(exclude_unset=True),
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return _to_schema(updated, *accommodation_service.room_occupancy(db, updated.id))


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá phòng")
def delete_room(
    room_id: int, event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request
) -> None:
    room = accommodation_service.get_room(db, event_id=event.id, room_id=room_id)
    accommodation_service.delete_room(
        db, event=event, room=room, actor=actor, ip_address=get_client_ip(request)
    )


@router.get("/{room_id}/occupants", response_model=list[OccupantOut], summary="Người đang ở phòng")
def list_occupants(room_id: int, event: ActiveEvent, db: DbSession) -> list[OccupantOut]:
    room = accommodation_service.get_room(db, event_id=event.id, room_id=room_id)
    return [OccupantOut(**row) for row in accommodation_service.list_occupants(db, room=room)]


def _to_schema(room: Room, occupied: int, has_captain: bool) -> RoomOut:
    # Dựng qua constructor (không model_copy) để gender_policy được validate thành enum.
    return RoomOut(
        **{
            **RoomOut.model_validate(room).model_dump(),
            "hotel_name": room.hotel.name if room.hotel else "",
            "occupied": occupied,
            "remaining": room.capacity - occupied,
            "has_captain": has_captain,
        }
    )


def _to_allocation_schema(
    result: RoomAllocationResult, *, dry_run: bool, removed_stale: int
) -> RoomAllocationResponse:
    """Dataclass của thuật toán -> response JSON (thuật toán là hàm thuần, không biết Pydantic)."""
    return RoomAllocationResponse(
        dry_run=dry_run,
        committed=not dry_run,
        summary=result.summary.__dict__,
        rooms=[
            {**load.__dict__, "guests": [guest.__dict__ for guest in load.guests]}
            for load in result.rooms
        ],
        unassigned=[guest.__dict__ for guest in result.unassigned],
        flags=[flag.__dict__ for flag in result.flags],
        params=result.params,
        removed_stale=removed_stale,
    )
