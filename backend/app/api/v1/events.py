"""Endpoint quản lý kỳ Team Building và vòng đời trạng thái."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.api.v1.email_jobs import schedule_emails
from app.core.dependencies import (
    ActiveEvent,
    AdminUser,
    CurrentUser,
    DbSession,
    Notify,
    get_client_ip,
    require_admin,
)
from app.models.enums import EventStatus
from app.models.event import Event
from app.schemas.event import (
    EventAdmin,
    EventCreate,
    EventPublic,
    EventStatusChange,
    EventStatusOverview,
    EventSettingsUpdate,
    EventUpdate,
    TermsResponse,
)
from app.services import event_service

router = APIRouter(prefix="/events", tags=["events"])


# --- CBNV ---


@router.get("/active", response_model=EventPublic, summary="Kỳ người dùng đang xem")
def get_active(event: ActiveEvent) -> EventPublic:
    """Kỳ mà request đang thao tác — theo `X-Event-Id`, không có thì kỳ mặc định.

    Đi qua đúng dependency mà mọi endpoint khác dùng, để frontend không bao giờ hiện tiêu đề của
    kỳ này trong khi dữ liệu bên dưới là của kỳ khác.
    """
    return _to_public(event)


@router.get(
    "/selectable",
    response_model=list[EventPublic],
    summary="Các kỳ người dùng được phép chọn",
)
def list_selectable(db: DbSession, user: CurrentUser) -> list[EventPublic]:
    """Nguồn dữ liệu cho bộ chọn kỳ. CBNV không thấy kỳ `draft`; BTC thấy hết.

    Đặt TRƯỚC `/{event_id}` trong file này là cố ý: FastAPI khớp route theo thứ tự khai báo, để sau
    thì "selectable" bị nuốt thành `event_id` và trả 422.
    """
    return [_to_public(event) for event in event_service.list_selectable_events(db, viewer=user)]


@router.get("/{event_id}/terms", response_model=TermsResponse, summary="Quy định chương trình")
def get_terms(event_id: int, db: DbSession, _: CurrentUser) -> TermsResponse:
    event = event_service.get_event(db, event_id)
    return TermsResponse(
        event_code=event.code,
        version=event.terms_version,
        content=event.terms_content or "Chưa có nội dung quy định.",
    )


# --- BTC ---


@router.get(
    "",
    response_model=list[EventAdmin],
    dependencies=[Depends(require_admin)],
    summary="Danh sách các kỳ",
)
def list_events(db: DbSession) -> list[EventAdmin]:
    return [_to_admin(event) for event in event_service.list_events(db)]


@router.post(
    "",
    response_model=EventAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo kỳ mới",
)
def create_event(
    payload: EventCreate, actor: AdminUser, db: DbSession, request: Request
) -> EventAdmin:
    event = event_service.create_event(
        db,
        data=payload.model_dump(exclude_unset=True),
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return _to_admin(event)


@router.get(
    "/{event_id}",
    response_model=EventAdmin,
    dependencies=[Depends(require_admin)],
    summary="Chi tiết một kỳ",
)
def get_event(event_id: int, db: DbSession) -> EventAdmin:
    return _to_admin(event_service.get_event(db, event_id))


@router.patch("/{event_id}", response_model=EventAdmin, summary="Sửa thông tin kỳ")
def update_event(
    event_id: int,
    payload: EventUpdate,
    actor: AdminUser,
    db: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
    notify: Notify = False,
) -> EventAdmin:
    event = event_service.get_event(db, event_id)
    updated, jobs = event_service.update_event(
        db,
        event=event,
        data=payload.model_dump(exclude_unset=True),
        actor=actor,
        notify=notify,
        ip_address=get_client_ip(request),
    )
    schedule_emails(background_tasks, jobs)
    return _to_admin(updated)


@router.post(
    "/{event_id}/activate",
    response_model=EventAdmin,
    summary="Đặt làm kỳ đang chạy",
)
def activate_event(
    event_id: int, actor: AdminUser, db: DbSession, request: Request
) -> EventAdmin:
    event = event_service.get_event(db, event_id)
    activated = event_service.activate_event(
        db, event=event, actor=actor, ip_address=get_client_ip(request)
    )
    return _to_admin(activated)


@router.post(
    "/{event_id}/status",
    response_model=EventAdmin,
    summary="Chuyển trạng thái chương trình",
)
def change_status(
    event_id: int,
    payload: EventStatusChange,
    actor: AdminUser,
    db: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
) -> EventAdmin:
    """Chuyển trạng thái theo đúng vòng đời, có kiểm tra điều kiện và ghi audit log."""
    event = event_service.get_event(db, event_id)
    updated, jobs = event_service.change_status(
        db,
        event=event,
        new_status=payload.status,
        actor=actor,
        reason=payload.reason,
        notify=payload.notify,
        ip_address=get_client_ip(request),
    )
    # Transaction đã commit trong service: giờ mới gửi thật, sau khi response trả về.
    schedule_emails(background_tasks, jobs)
    return _to_admin(updated)


@router.get(
    "/{event_id}/overview",
    response_model=EventStatusOverview,
    dependencies=[Depends(require_admin)],
    summary="Tổng quan trạng thái",
)
def get_overview(event_id: int, db: DbSession) -> EventStatusOverview:
    event = event_service.get_event(db, event_id)
    data = event_service.get_status_overview(db, event)
    return EventStatusOverview(
        **data, status_label=event_service.status_label(data["status"])
    )


@router.get(
    "/{event_id}/settings",
    dependencies=[Depends(require_admin)],
    summary="Cấu hình kỳ (trọng số thuật toán, thời gian giữ ghế...)",
)
def get_settings(event_id: int, db: DbSession) -> dict:
    event_service.get_event(db, event_id)  # 404 nếu không tồn tại
    return event_service.get_settings(db, event_id)


@router.put("/{event_id}/settings", summary="Cập nhật cấu hình kỳ")
def update_settings(
    event_id: int,
    payload: EventSettingsUpdate,
    actor: AdminUser,
    db: DbSession,
    request: Request,
) -> dict:
    event = event_service.get_event(db, event_id)
    return event_service.update_settings(
        db,
        event=event,
        values=payload.values,
        actor=actor,
        ip_address=get_client_ip(request),
    )


# --- Chuyển đổi sang schema ---


def _derived(event: Event) -> dict:
    current = EventStatus(event.status)
    return {
        "status_label": event_service.status_label(event.status),
        "can_register": current == EventStatus.REGISTRATION_OPEN,
        "is_published": current.at_least(EventStatus.INFORMATION_PUBLISHED),
    }


def _to_public(event: Event) -> EventPublic:
    return EventPublic.model_validate(event).model_copy(update=_derived(event))


def _to_admin(event: Event) -> EventAdmin:
    return EventAdmin.model_validate(event).model_copy(update=_derived(event))
