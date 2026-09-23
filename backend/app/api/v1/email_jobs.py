"""Xếp email đã `enqueue` vào BackgroundTask — chỉ sau khi transaction ghi thư đã commit.

Dùng chung cho mọi router có ô "Gửi email báo CBNV" (`notify`).
"""

from fastapi import BackgroundTasks, Request

from app.core.dependencies import get_client_ip
from app.models.user import User
from app.services import email_service
from app.services.journey_notice_service import JourneyTracker


def schedule_emails(background_tasks: BackgroundTasks, jobs: list[dict]) -> None:
    for job in jobs:
        background_tasks.add_task(email_service.deliver_queued_async, **job)


def send_journey_notices(
    background_tasks: BackgroundTasks,
    tracker: JourneyTracker,
    actor: User,
    request: Request,
    action: str,
) -> None:
    """Chụp hành trình SAU thao tác, so với lúc trước, xếp thư cho đúng người bị đổi."""
    schedule_emails(
        background_tasks,
        tracker.finish(actor=actor, action=action, ip_address=get_client_ip(request)),
    )
