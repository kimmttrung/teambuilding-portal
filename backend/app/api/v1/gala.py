"""Gala Dinner (Module 4, docs/04-api-spec.md §8).

- 🟢 Mọi người đăng nhập: xem sơ đồ, thứ tự bốc thăm, luồng SSE.
- 🔵 Trưởng nhóm của team đang tới lượt: giữ / nhả / xác nhận ghế; xếp thành viên vào ghế team
  (từng người hoặc ngẫu nhiên). Kiểm tra "có phải trưởng nhóm của team này" nằm ở service.
- 🔴 BTC: cấu hình sơ đồ, bốc thăm, điều khiển lượt, mở lại chọn ghế, ép gán / khoá ghế.

Các thao tác chọn ghế của team chỉ mở khi BTC đã công bố thông tin (docs/01-requirements.md §3).
Mutation của BTC trả luôn sơ đồ mới để màn hình không phải gọi thêm một request.

Email báo Trưởng nhóm tới lượt: service ghi dòng `queued` trong transaction chuyển lượt và trả
`jobs`, router gửi sau khi response trả về. Lượt có thể bắt đầu ở bất kỳ request nào dọn lazy (xem
sơ đồ, SSE, hết giờ), nên mọi endpoint có dọn lazy đều nhận `BackgroundTasks`.
"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.core import database
from app.core.dependencies import (
    ActiveEvent,
    AdminUser,
    CurrentUser,
    DbSession,
    get_client_ip,
    require_published_event,
)
from app.models.event import Event
from app.models.user import User
from app.schemas.gala import (
    AssignMemberOut,
    AssignMemberRequest,
    AutoAssignOut,
    AutoAssignRequest,
    ConfirmResultOut,
    DrawRequest,
    DrawStateOut,
    GalaLayoutIn,
    GalaLayoutUpdate,
    GalaTableIn,
    GalaTableUpdate,
    GalaViewOut,
    HoldResultOut,
    MyTurnOut,
    ReleaseResultOut,
    SeatAdminUpdate,
    SeatHoldRequest,
    TeamMemberOut,
    TurnNextRequest,
    UnseatedParticipantOut,
)
from app.services import email_service, gala_service, gala_stream

router = APIRouter(prefix="/gala", tags=["gala"])

PublishedEvent = Annotated[Event, Depends(require_published_event)]
Jobs = list[dict[str, Any]]


def _send(background_tasks: BackgroundTasks, jobs: Jobs) -> None:
    for job in jobs:
        background_tasks.add_task(email_service.deliver_queued_async, **job)


def _view(db, event: Event, viewer: User, background_tasks: BackgroundTasks) -> GalaViewOut:
    jobs: Jobs = []
    data = gala_service.build_view(db, event=event, viewer=viewer, jobs=jobs)
    _send(background_tasks, jobs)
    return GalaViewOut(**data)


# --- Xem ---


@router.get("/layout", response_model=GalaViewOut, summary="Sơ đồ Gala + trạng thái từng ghế")
def get_layout(
    event: ActiveEvent, db: DbSession, user: CurrentUser, background_tasks: BackgroundTasks
) -> GalaViewOut:
    """Trạng thái ghế: available · held_by_me · held_by_other · taken · unavailable.

    Tên người ngồi chỉ có với BTC và thành viên team sở hữu ghế.
    """
    return _view(db, event, user, background_tasks)


@router.get("/draw-orders", response_model=DrawStateOut, summary="Thứ tự bốc thăm + team đang tới lượt")
def get_draw_orders(
    event: ActiveEvent, db: DbSession, user: CurrentUser, background_tasks: BackgroundTasks
) -> DrawStateOut:
    jobs: Jobs = []
    data = gala_service.draw_state(db, event=event, viewer=user, jobs=jobs)
    _send(background_tasks, jobs)
    return DrawStateOut(**data)


@router.get("/my-turn", response_model=MyTurnOut, summary="Lượt chọn ghế của team mình (banner nhắc Trưởng nhóm)")
def get_my_turn(
    event: ActiveEvent, db: DbSession, user: CurrentUser, background_tasks: BackgroundTasks
) -> MyTurnOut:
    """Nhẹ hơn `/gala/layout` — giao diện hỏi định kỳ ở mọi trang để báo "đến lượt team bạn"."""
    jobs: Jobs = []
    data = gala_service.my_turn(db, event=event, user=user, jobs=jobs)
    _send(background_tasks, jobs)
    return MyTurnOut(**data)


@router.get("/stream", summary="SSE: báo sơ đồ vừa thay đổi")
async def stream(request: Request, event: ActiveEvent, user: CurrentUser, db: DbSession) -> StreamingResponse:
    """Sự kiện `change` mang `{version}` — nhận được thì tải lại `/gala/layout`. Không chứa dữ liệu ghế."""
    event_id = event.id
    # Luồng sống nhiều phút: trả kết nối DB của request ngay, mỗi nhịp tự mở session ngắn.
    db.close()

    def read_version() -> str:
        jobs: Jobs = []
        with database.session_scope() as session:
            version = gala_service.change_signature(session, event_id=event_id, jobs=jobs)
        # Nhịp này vừa chuyển lượt (hết giờ): gửi email ngay trong luồng phụ, session đã đóng.
        for job in jobs:
            email_service.deliver_queued_async(**job)
        return version

    async def poll() -> str:
        return await run_in_threadpool(read_version)

    return StreamingResponse(
        gala_stream.change_events(poll=poll, is_disconnected=request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/team-members", response_model=list[TeamMemberOut], summary="Thành viên team kèm ghế Gala")
def get_team_members(
    event: ActiveEvent,
    db: DbSession,
    user: CurrentUser,
    team_id: int | None = Query(default=None, description="Chỉ BTC dùng; Trưởng nhóm luôn xem team mình"),
) -> list[TeamMemberOut]:
    return [TeamMemberOut(**row) for row in gala_service.team_members(db, event=event, viewer=user, team_id=team_id)]


@router.get(
    "/unseated",
    response_model=list[UnseatedParticipantOut],
    summary="Người tham gia chưa có ghế (gồm cả người chưa thuộc team nào)",
)
def get_unseated_participants(
    event: ActiveEvent, db: DbSession, user: CurrentUser
) -> list[UnseatedParticipantOut]:
    return [
        UnseatedParticipantOut(**row)
        for row in gala_service.unseated_participants(db, event=event, viewer=user)
    ]


# --- Trưởng nhóm ---


@router.post("/seats/hold", response_model=HoldResultOut, summary="Giữ ghế tạm cho team đang tới lượt")
def hold_seats(payload: SeatHoldRequest, event: PublishedEvent, db: DbSession, user: CurrentUser) -> HoldResultOut:
    return HoldResultOut(**gala_service.hold_seats(db, event=event, user=user, seat_ids=payload.seat_ids))


@router.delete("/seats/hold", response_model=ReleaseResultOut, summary="Nhả ghế team đang giữ")
def release_holds(
    event: ActiveEvent,
    db: DbSession,
    user: CurrentUser,
    seat_ids: list[int] | None = Query(default=None, description="Bỏ trống = nhả tất cả"),
) -> ReleaseResultOut:
    return ReleaseResultOut(released=gala_service.release_holds(db, event=event, user=user, seat_ids=seat_ids))


@router.post("/seats/confirm", response_model=ConfirmResultOut, summary="Xác nhận mọi ghế team đang giữ")
def confirm_seats(
    event: PublishedEvent, db: DbSession, user: CurrentUser, request: Request, background_tasks: BackgroundTasks
) -> ConfirmResultOut:
    jobs: Jobs = []
    result = gala_service.confirm_seats(db, event=event, user=user, jobs=jobs, ip_address=get_client_ip(request))
    _send(background_tasks, jobs)
    return ConfirmResultOut(**result)


@router.post("/seats/assign-member", response_model=AssignMemberOut, summary="Gán thành viên vào ghế của team")
def assign_member(
    payload: AssignMemberRequest, event: PublishedEvent, db: DbSession, user: CurrentUser, request: Request
) -> AssignMemberOut:
    return AssignMemberOut(
        **gala_service.assign_member(
            db,
            event=event,
            actor=user,
            seat_id=payload.seat_id,
            registration_id=payload.registration_id,
            ip_address=get_client_ip(request),
        )
    )


@router.post("/seats/auto-assign", response_model=AutoAssignOut, summary="Xếp ngẫu nhiên thành viên vào ghế team")
def auto_assign_members(
    payload: AutoAssignRequest, event: PublishedEvent, db: DbSession, user: CurrentUser, request: Request
) -> AutoAssignOut:
    """Mặc định chỉ xếp người chưa có ghế; `reshuffle=true` xáo lại cả team. Đổi chỗ từng người sau
    đó bằng `/seats/assign-member`."""
    return AutoAssignOut(
        **gala_service.auto_assign_members(
            db,
            event=event,
            actor=user,
            team_id=payload.team_id,
            reshuffle=payload.reshuffle,
            ip_address=get_client_ip(request),
        )
    )


# --- BTC ---


@router.post("/layout", response_model=GalaViewOut, status_code=status.HTTP_201_CREATED, summary="Tạo sơ đồ Gala")
def create_layout(
    payload: GalaLayoutIn,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> GalaViewOut:
    gala_service.create_layout(db, event=event, data=payload.model_dump(), actor=actor, ip_address=get_client_ip(request))
    return _view(db, event, actor, background_tasks)


@router.patch("/layout", response_model=GalaViewOut, summary="Sửa thông tin sơ đồ")
def update_layout(
    payload: GalaLayoutUpdate,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> GalaViewOut:
    gala_service.update_layout(
        db, event=event, data=payload.model_dump(exclude_unset=True), actor=actor, ip_address=get_client_ip(request)
    )
    return _view(db, event, actor, background_tasks)


@router.post("/tables", response_model=GalaViewOut, status_code=status.HTTP_201_CREATED, summary="Thêm bàn")
def create_table(
    payload: GalaTableIn,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> GalaViewOut:
    gala_service.create_table(db, event=event, data=payload.model_dump(), actor=actor, ip_address=get_client_ip(request))
    return _view(db, event, actor, background_tasks)


@router.patch("/tables/{table_id}", response_model=GalaViewOut, summary="Sửa bàn (vị trí, số ghế, khoá bàn)")
def update_table(
    table_id: int,
    payload: GalaTableUpdate,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> GalaViewOut:
    gala_service.update_table(
        db,
        event=event,
        table_id=table_id,
        data=payload.model_dump(exclude_unset=True),
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return _view(db, event, actor, background_tasks)


@router.delete("/tables/{table_id}", response_model=GalaViewOut, summary="Xoá bàn chưa có ghế thuộc team")
def delete_table(
    table_id: int,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> GalaViewOut:
    gala_service.delete_table(db, event=event, table_id=table_id, actor=actor, ip_address=get_client_ip(request))
    return _view(db, event, actor, background_tasks)


@router.post("/draw", response_model=GalaViewOut, summary="Bốc thăm thứ tự team (lưu seed)")
def draw(
    payload: DrawRequest,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> GalaViewOut:
    """Quota mỗi team = số thành viên đã xác nhận tham gia. Bốc lại được khi chưa mở chọn ghế."""
    gala_service.draw(db, event=event, actor=actor, seed=payload.seed, ip_address=get_client_ip(request))
    return _view(db, event, actor, background_tasks)


@router.post("/turn/next", response_model=GalaViewOut, summary="Mở chọn ghế / chuyển lượt")
def next_turn(
    payload: TurnNextRequest,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> GalaViewOut:
    jobs: Jobs = []
    gala_service.advance_turn(
        db, event=event, actor=actor, jobs=jobs, skip=payload.skip, ip_address=get_client_ip(request)
    )
    _send(background_tasks, jobs)
    return _view(db, event, actor, background_tasks)


@router.post("/reopen", response_model=GalaViewOut, summary="Mở lại chọn ghế cho team chưa đủ ghế")
def reopen(
    event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request, background_tasks: BackgroundTasks
) -> GalaViewOut:
    """Chỉ khi đã kết thúc. Team chưa đủ ghế chọn lại theo thứ tự đã bốc thăm, team đủ ghế giữ nguyên."""
    jobs: Jobs = []
    gala_service.reopen(db, event=event, actor=actor, jobs=jobs, ip_address=get_client_ip(request))
    _send(background_tasks, jobs)
    return _view(db, event, actor, background_tasks)


@router.post("/finalize", response_model=GalaViewOut, summary="Kết thúc chọn ghế")
def finalize(
    event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request, background_tasks: BackgroundTasks
) -> GalaViewOut:
    gala_service.finalize(db, event=event, actor=actor, ip_address=get_client_ip(request))
    return _view(db, event, actor, background_tasks)


@router.patch("/seats/{seat_id}", response_model=GalaViewOut, summary="BTC ép gán / gỡ / khoá ghế")
def update_seat(
    seat_id: int,
    payload: SeatAdminUpdate,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> GalaViewOut:
    data = payload.model_dump(include={"team_id", "registration_id", "is_available"}, exclude_unset=True)
    gala_service.admin_update_seat(
        db,
        event=event,
        actor=actor,
        seat_id=seat_id,
        data=data,
        reason=payload.reason,
        ip_address=get_client_ip(request),
    )
    return _view(db, event, actor, background_tasks)
