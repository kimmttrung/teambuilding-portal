"""Endpoint đăng ký tham gia Team Building (Module 1)."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.core.dependencies import (
    ActiveEvent,
    CurrentUser,
    DbSession,
    ensure_can_access_user,
    get_client_ip,
    require_admin,
)
from app.models.enums import RegistrationStatus
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import User
from app.schemas.common import Page
from app.schemas.registration import (
    BusNeedOut,
    RegistrationAdminOut,
    RegistrationCancel,
    RegistrationCreate,
    RegistrationOut,
    RegistrationPersonBrief,
    RegistrationStats,
    RegistrationUpdate,
    ShiftBrief,
)
from app.services import email_service, email_templates, registration_service

router = APIRouter(prefix="/registrations", tags=["registrations"])


# --- CBNV ---


@router.get("/me", response_model=RegistrationOut, summary="Đăng ký của tôi")
def get_my_registration(
    user: CurrentUser, event: ActiveEvent, db: DbSession
) -> RegistrationOut:
    registration = registration_service.require_registration(
        db, event_id=event.id, user_id=user.id
    )
    return _to_schema(db, event, registration)


@router.post(
    "",
    response_model=RegistrationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Gửi đăng ký",
)
def submit_registration(
    payload: RegistrationCreate,
    user: CurrentUser,
    event: ActiveEvent,
    db: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
) -> RegistrationOut:
    registration = registration_service.submit(
        db,
        event=event,
        user=user,
        data=payload.model_dump(exclude_unset=False),
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _queue_email(background_tasks, "registration_confirmed", event, user, registration)
    return _to_schema(db, event, registration)


@router.patch("/me", response_model=RegistrationOut, summary="Sửa đăng ký của tôi")
def update_my_registration(
    payload: RegistrationUpdate,
    user: CurrentUser,
    event: ActiveEvent,
    db: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
) -> RegistrationOut:
    registration = registration_service.require_registration(
        db, event_id=event.id, user_id=user.id
    )
    updated = registration_service.update(
        db,
        event=event,
        user=user,
        registration=registration,
        data=payload.model_dump(exclude_unset=True),
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _queue_email(background_tasks, "registration_updated", event, user, updated)
    return _to_schema(db, event, updated)


@router.post("/me/cancel", response_model=RegistrationOut, summary="Huỷ đăng ký")
def cancel_my_registration(
    payload: RegistrationCancel,
    user: CurrentUser,
    event: ActiveEvent,
    db: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
) -> RegistrationOut:
    registration = registration_service.require_registration(
        db, event_id=event.id, user_id=user.id
    )
    cancelled = registration_service.cancel(
        db,
        event=event,
        user=user,
        registration=registration,
        reason=payload.reason,
        ip_address=get_client_ip(request),
    )
    _queue_email(background_tasks, "registration_cancelled", event, user, cancelled)
    return _to_schema(db, event, cancelled)


# --- BTC ---


@router.get(
    "",
    response_model=Page[RegistrationAdminOut],
    dependencies=[Depends(require_admin)],
    summary="Danh sách đăng ký",
)
def list_registrations(
    event: ActiveEvent,
    db: DbSession,
    q: str | None = Query(default=None, description="Tìm theo tên, email, mã nhân viên"),
    team_id: int | None = None,
    shift_id: int | None = None,
    reg_status: RegistrationStatus | None = Query(default=None, alias="status"),
    is_participating: bool | None = None,
    missing_documents: bool | None = Query(
        default=None, description="Chỉ lấy người thiếu CCCD/ngày sinh"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[RegistrationAdminOut]:
    rows, total = registration_service.list_registrations(
        db,
        event_id=event.id,
        search=q,
        team_id=team_id,
        shift_id=shift_id,
        status=reg_status.value if reg_status else None,
        is_participating=is_participating,
        missing_documents=missing_documents,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=[_to_admin_schema(db, event, row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stats",
    response_model=RegistrationStats,
    dependencies=[Depends(require_admin)],
    summary="Thống kê đăng ký",
)
def get_stats(event: ActiveEvent, db: DbSession) -> RegistrationStats:
    return RegistrationStats(**registration_service.get_stats(db, event_id=event.id))


@router.get(
    "/{user_id}",
    response_model=RegistrationAdminOut,
    summary="Đăng ký của một CBNV",
)
def get_registration_of_user(
    user_id: int, current_user: CurrentUser, event: ActiveEvent, db: DbSession
) -> RegistrationAdminOut:
    # Lớp 2 của phân quyền: CBNV chỉ xem được chính mình (docs/09-security.md §2).
    ensure_can_access_user(current_user, user_id)
    registration = registration_service.require_registration(
        db, event_id=event.id, user_id=user_id
    )
    return _to_admin_schema(db, event, registration)


# --- Email ---


def _queue_email(
    background_tasks: BackgroundTasks,
    template: str,
    event: Event,
    user: User,
    registration: Registration,
) -> None:
    """Xếp email vào BackgroundTask — gửi SAU khi response đã trả về.

    Gọi SMTP ngay trong request nghĩa là CBNV phải chờ mail đi xong mới thấy trang
    thành công, và SMTP chậm sẽ thành lỗi timeout của việc đăng ký.
    Context phải dựng ở đây (session còn sống), không dựng trong background task.
    """
    context = email_templates.registration_context(
        event=event,
        user=user,
        registration=registration,
        missing_profile_fields=registration_service.missing_profile_fields(user),
    )
    background_tasks.add_task(
        email_service.send_async,
        template=template,
        to_email=user.email,
        context=context,
        user_id=user.id,
        related_type="registration",
        related_id=registration.id,
    )


# --- Chuyển đổi sang schema ---


def _bus_needs(registration: Registration) -> list[BusNeedOut]:
    return [
        BusNeedOut(
            trip_leg_id=need.trip_leg_id,
            trip_leg_code=need.trip_leg.code if need.trip_leg else "",
            trip_leg_name=need.trip_leg.name if need.trip_leg else "",
            needs_bus=need.needs_bus,
            pickup_point_id=need.pickup_point_id,
            pickup_point_name=need.pickup_point.name if need.pickup_point else None,
            note=need.note,
        )
        for need in sorted(
            registration.bus_needs,
            key=lambda item: item.trip_leg.display_order if item.trip_leg else 0,
        )
    ]


def _to_schema(db, event: Event, registration: Registration) -> RegistrationOut:
    return RegistrationOut.model_validate(registration).model_copy(
        update={
            "shift": ShiftBrief.model_validate(registration.shift)
            if registration.shift
            else None,
            "bus_needs": _bus_needs(registration),
            "can_edit": registration_service.can_edit(event, registration),
            "agreed_terms_version": registration_service.get_consent_version(
                db, event_id=event.id, user_id=registration.user_id
            ),
        }
    )


def _to_admin_schema(db, event: Event, registration: Registration) -> RegistrationAdminOut:
    base = _to_schema(db, event, registration)
    user = registration.user
    person = RegistrationPersonBrief.model_validate(user).model_copy(
        update={
            "team_name": user.team.name if user.team else None,
            "can_fly": user.can_fly,
        }
    )
    return RegistrationAdminOut(
        **base.model_dump(),
        user=person,
        has_consent=base.agreed_terms_version is not None,
    )
