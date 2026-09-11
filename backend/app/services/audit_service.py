"""Ghi nhật ký thay đổi.

Yêu cầu nghiệp vụ cứng: BTC phải giải thích được vì sao một CBNV bị đổi chuyến bay,
ai đóng đăng ký lúc mấy giờ. Log ghi trong CÙNG transaction với thay đổi — nếu thay đổi
bị rollback thì log cũng biến mất, không để lại dấu vết sai sự thật.
"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow_iso
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

# Trường nhạy cảm không bao giờ được sao chép vào audit log.
REDACTED_FIELDS = {
    "password_hash",
    "token_hash",
    "id_card_number",
    "health_note",
    "jti",
}


def log(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    actor_id: int | None = None,
    event_id: int | None = None,
    before: Any = None,
    after: Any = None,
    reason: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Thêm một dòng audit vào session hiện tại (chưa commit).

    `action` theo dạng "<đối tượng>.<hành động>": event.status_changed, flight.reassign.
    """
    entry = AuditLog(
        event_id=event_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=_serialize(before),
        after_data=_serialize(after),
        reason=reason,
        ip_address=ip_address,
        created_at=utcnow_iso(),
    )
    db.add(entry)
    logger.info("audit %s %s#%s bởi user=%s", action, entity_type, entity_id, actor_id)
    return entry


def snapshot(instance: Any, fields: list[str]) -> dict[str, Any]:
    """Chụp giá trị một số trường của ORM object để so sánh trước/sau."""
    return {
        field: ("***" if field in REDACTED_FIELDS else getattr(instance, field, None))
        for field in fields
    }


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Chỉ giữ lại những trường thực sự đổi — log gọn và dễ đọc hơn."""
    return {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    }


def list_logs(
    db: Session,
    *,
    event_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    """Đọc nhật ký có lọc. Trả (danh sách, tổng số)."""
    query = select(AuditLog)
    filters = {
        AuditLog.event_id: event_id,
        AuditLog.entity_type: entity_type,
        AuditLog.entity_id: entity_id,
        AuditLog.actor_id: actor_id,
        AuditLog.action: action,
    }
    for column, value in filters.items():
        if value is not None:
            query = query.where(column == value)

    total = len(list(db.scalars(query)))
    rows = list(
        db.scalars(query.order_by(AuditLog.id.desc()).limit(limit).offset(offset))
    )
    return rows, total


def _serialize(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)
