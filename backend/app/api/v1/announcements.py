"""Thông báo BTC gửi CBNV: soạn nháp, xem trước người nhận, đăng, gỡ, xoá.

Luồng hai bước giống email nhắc việc: soạn nháp trước (kèm số người sẽ nhận), bấm
đăng mới hiện trong My Journey — tick thêm "gửi email" thì xếp thư cho đúng nhóm
đối tượng sau khi transaction đã commit.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.core.config import settings
from app.core.dependencies import ActiveEvent, AdminUser, DbSession, get_client_ip, require_admin
from app.models.enums import AnnouncementTarget
from app.schemas.announcement import (
    AnnouncementIn,
    AnnouncementOut,
    AnnouncementPublish,
    AnnouncementPublishResult,
    AnnouncementUpdate,
    RecipientPreview,
)
from app.services import announcement_service, audit_service, email_service

router = APIRouter(
    prefix="/admin/announcements",
    tags=["announcements"],
    dependencies=[Depends(require_admin)],
)


def _audit(db, request, actor, action, entity_id, before=None, after=None) -> None:
    audit_service.log(
        db,
        action=action,
        entity_type="announcement",
        entity_id=entity_id,
        actor_id=actor.id,
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    db.commit()


def _to_out(db, event, item) -> AnnouncementOut:
    return AnnouncementOut(**announcement_service.get_out(db, event, item.id))


@router.get("", response_model=list[AnnouncementOut], summary="Toàn bộ thông báo của kỳ")
def list_announcements(event: ActiveEvent, db: DbSession, _: AdminUser) -> list[AnnouncementOut]:
    return [
        AnnouncementOut(**row) for row in announcement_service.list_announcements(db, event)
    ]


@router.get("/recipients", response_model=RecipientPreview, summary="Xem trước ai sẽ nhận")
def preview_recipients(
    target_type: AnnouncementTarget,
    event: ActiveEvent,
    db: DbSession,
    _: AdminUser,
    target_id: int | None = None,
) -> RecipientPreview:
    return RecipientPreview(
        **announcement_service.recipient_preview(db, event, target_type, target_id)
    )


@router.post(
    "", response_model=AnnouncementOut, status_code=status.HTTP_201_CREATED, summary="Soạn nháp"
)
def create_announcement(
    payload: AnnouncementIn, event: ActiveEvent, actor: AdminUser, db: DbSession, request: Request
) -> AnnouncementOut:
    item = announcement_service.create_announcement(
        db, event, payload.model_dump(), actor_id=actor.id
    )
    _audit(db, request, actor, "announcement.created", item.id, after=payload.model_dump())
    return _to_out(db, event, item)


@router.patch("/{item_id}", response_model=AnnouncementOut, summary="Sửa thông báo")
def update_announcement(
    item_id: int,
    payload: AnnouncementUpdate,
    event: ActiveEvent,
    actor: AdminUser,
    db: DbSession,
    request: Request,
) -> AnnouncementOut:
    changes = payload.model_dump(exclude_unset=True)
    item = announcement_service.update_announcement(db, event, item_id, changes)
    _audit(db, request, actor, "announcement.updated", item_id, after=changes)
    return _to_out(db, event, item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá thông báo")
def delete_announcement(
    item_id: int, event: ActiveEvent, actor: AdminUser, db: DbSession, request: Request
) -> None:
    item = announcement_service.delete_announcement(db, event, item_id)
    _audit(
        db, request, actor, "announcement.deleted", item_id, before={"title": item.title}
    )


@router.post("/{item_id}/publish", response_model=AnnouncementPublishResult, summary="Đăng")
def publish_announcement(
    item_id: int,
    payload: AnnouncementPublish,
    actor: AdminUser,
    event: ActiveEvent,
    db: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
) -> AnnouncementPublishResult:
    _item, result, jobs = announcement_service.publish(
        db,
        event=event,
        item_id=item_id,
        actor=actor,
        send_email=payload.send_email,
        ip_address=get_client_ip(request),
    )
    # Transaction đã commit trong service: giờ mới gửi thật, sau khi response trả về.
    for job in jobs:
        background_tasks.add_task(email_service.deliver_queued_async, **job)
    return AnnouncementPublishResult(
        **result, email_enabled=settings.EMAIL_ENABLED
    )


@router.post("/{item_id}/unpublish", response_model=AnnouncementOut, summary="Gỡ về nháp")
def unpublish_announcement(
    item_id: int, event: ActiveEvent, actor: AdminUser, db: DbSession, request: Request
) -> AnnouncementOut:
    item = announcement_service.unpublish(db, event, item_id)
    _audit(db, request, actor, "announcement.unpublished", item_id)
    return _to_out(db, event, item)
