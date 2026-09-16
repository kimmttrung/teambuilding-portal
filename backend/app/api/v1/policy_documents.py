"""Tài liệu chương trình (FAQ, hướng dẫn) — BTC soạn, chatbot Tibi đọc.

CBNV không gọi các endpoint này: họ hỏi Tibi hoặc đọc quy định qua `/events/{id}/terms`.
"""

from fastapi import APIRouter, Request, status

from app.core.dependencies import ActiveEvent, AdminUser, DbSession, get_client_ip
from app.models.content import PolicyDocument
from app.schemas.policy_document import (
    PolicyDocumentIn,
    PolicyDocumentOut,
    PolicyDocumentUpdate,
)
from app.services import audit_service, policy_document_service

router = APIRouter(prefix="/admin/documents", tags=["documents"])


def _audit(db, request, actor, action, entity_id, before=None, after=None) -> None:
    audit_service.log(
        db,
        action=action,
        entity_type="policy_document",
        entity_id=entity_id,
        actor_id=actor.id,
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    db.commit()


def _to_out(document: PolicyDocument, actor) -> PolicyDocumentOut:
    return PolicyDocumentOut.model_validate(document).model_copy(
        update={
            "is_shared": document.event_id is None,
            "can_edit": policy_document_service.can_edit(document, actor),
        }
    )


@router.get("", response_model=list[PolicyDocumentOut], summary="Tài liệu của kỳ + dùng chung")
def list_documents(event: ActiveEvent, db: DbSession, actor: AdminUser) -> list[PolicyDocumentOut]:
    return [
        _to_out(item, actor)
        for item in policy_document_service.list_documents(db, event)
    ]


@router.post(
    "",
    response_model=PolicyDocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm tài liệu",
)
def create_document(
    payload: PolicyDocumentIn,
    event: ActiveEvent,
    actor: AdminUser,
    db: DbSession,
    request: Request,
) -> PolicyDocumentOut:
    document = policy_document_service.create_document(db, event, payload.model_dump())
    _audit(
        db, request, actor, "document.created", document.id,
        after=policy_document_service.snapshot(document),
    )
    return _to_out(document, actor)


@router.patch("/{document_id}", response_model=PolicyDocumentOut, summary="Sửa tài liệu")
def update_document(
    document_id: int,
    payload: PolicyDocumentUpdate,
    event: ActiveEvent,
    actor: AdminUser,
    db: DbSession,
    request: Request,
) -> PolicyDocumentOut:
    changes = payload.model_dump(exclude_unset=True)
    before = policy_document_service.snapshot(
        policy_document_service.get_document(db, event, document_id)
    )
    document = policy_document_service.update_document(
        db, event, document_id, changes, actor=actor
    )
    _audit(
        db, request, actor, "document.updated", document.id,
        before=before, after=policy_document_service.snapshot(document),
    )
    return _to_out(document, actor)


@router.delete(
    "/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá tài liệu"
)
def delete_document(
    document_id: int,
    event: ActiveEvent,
    actor: AdminUser,
    db: DbSession,
    request: Request,
) -> None:
    before = policy_document_service.delete_document(db, event, document_id, actor=actor)
    _audit(db, request, actor, "document.deleted", document_id, before=before)
