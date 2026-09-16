"""CRUD tài liệu chương trình (`policy_documents`): FAQ và hướng dẫn.

Đây là **nguồn kiến thức của chatbot Tibi** (docs/06-rag-chatbot.md §5), nên chỉ chứa nội dung công
khai với mọi CBNV — không bao giờ có dữ liệu cá nhân. Sửa xong phải nạp lại kiến thức
(`POST /admin/rag/reindex`) thì Tibi mới trả lời theo bản mới; `is_indexed` bị hạ về false ngay khi
sửa để BTC nhìn ra tài liệu nào đang lệch với thứ Tibi đang đọc.

Hai loại KHÔNG quản ở đây, vì mỗi thứ đã có một nguồn sự thật riêng:
- `terms` — quy định nằm ở `events.terms_content`, gắn với `terms_version` mà CBNV đã đồng ý.
- `itinerary` — lịch trình nằm ở bảng `itinerary_items`, có màn hình riêng.
Cho phép tạo trùng ở đây là tự tạo ra hai bản quy định khác nhau, rồi không ai biết bản nào đúng.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.timeutils import utcnow_iso
from app.models.content import PolicyDocument
from app.models.enums import ADMIN_ROLES, PolicyDocType, UserRole
from app.models.event import Event
from app.models.user import User

# Loại tài liệu BTC được tạo/sửa ở màn hình này.
EDITABLE_TYPES = (PolicyDocType.FAQ, PolicyDocType.GUIDE)

_ELSEWHERE = {
    PolicyDocType.TERMS: 'Quy định chương trình sửa ở tab "Quy định" (gắn với terms_version).',
    PolicyDocType.ITINERARY: "Lịch trình sửa ở màn hình Lịch trình.",
}


def list_documents(db: Session, event: Event) -> list[PolicyDocument]:
    """Tài liệu của kỳ + tài liệu dùng chung (`event_id` NULL), dùng chung xếp sau."""
    return list(
        db.scalars(
            select(PolicyDocument)
            .where(
                # `IN (id, NULL)` KHÔNG khớp dòng NULL — so sánh với NULL luôn cho UNKNOWN.
                # Phải viết rời bằng or_ thì tài liệu dùng chung mới lọt vào danh sách.
                or_(PolicyDocument.event_id == event.id, PolicyDocument.event_id.is_(None)),
                PolicyDocument.doc_type.in_(list(EDITABLE_TYPES)),
            )
            .order_by(PolicyDocument.event_id.is_(None), PolicyDocument.doc_type, PolicyDocument.id)
        )
    )


def create_document(db: Session, event: Event, data: dict) -> PolicyDocument:
    _require_editable_type(data["doc_type"])
    document = PolicyDocument(
        event_id=event.id,
        doc_type=data["doc_type"],
        title=data["title"].strip(),
        content=data["content"],
        version=data.get("version") or "v1",
        is_indexed=False,
        updated_at=utcnow_iso(),
    )
    db.add(document)
    db.flush()
    return document


def update_document(
    db: Session, event: Event, document_id: int, changes: dict, *, actor: User
) -> PolicyDocument:
    document = get_document(db, event, document_id)
    _require_can_edit_shared(document, actor)
    if "doc_type" in changes:
        _require_editable_type(changes["doc_type"])

    for field, value in changes.items():
        setattr(document, field, value.strip() if field == "title" else value)

    # Nội dung đổi thì bản trong vector store đã cũ — hạ cờ để BTC thấy cần nạp lại kiến thức.
    document.is_indexed = False
    document.updated_at = utcnow_iso()
    db.flush()
    return document


def delete_document(db: Session, event: Event, document_id: int, *, actor: User) -> dict:
    """Trả ảnh chụp để ghi audit — chụp TRƯỚC khi xoá.

    Đọc thuộc tính của một ORM object đã bị xoá và flush thì SQLAlchemy ném lỗi, nên không thể trả
    object ra cho router tự chụp (cùng họ với cạm bẫy `DetachedInstanceError` ở CLAUDE.md #10).
    """
    document = get_document(db, event, document_id)
    _require_can_edit_shared(document, actor)
    before = snapshot(document)
    db.delete(document)
    db.flush()
    return before


def snapshot(document: PolicyDocument) -> dict:
    """Ảnh chụp cho audit. KHÔNG kèm `content`: tài liệu dài vài nghìn ký tự, nhét cả vào audit log
    thì bảng phình rất nhanh mà không ai đọc lại từ đó."""
    return {
        "id": document.id,
        "doc_type": document.doc_type,
        "title": document.title,
        "version": document.version,
        "content_length": len(document.content or ""),
        "is_shared": document.event_id is None,
    }


def get_document(db: Session, event: Event, document_id: int) -> PolicyDocument:
    document = db.get(PolicyDocument, document_id)
    if document is None or document.event_id not in (event.id, None):
        raise NotFoundError(
            f"Không tìm thấy tài liệu #{document_id} trong kỳ này.", code="DOCUMENT_NOT_FOUND"
        )
    if document.doc_type not in EDITABLE_TYPES:
        raise ConflictError(
            _ELSEWHERE.get(document.doc_type, "Loại tài liệu này không sửa ở đây."),
            code="DOCUMENT_TYPE_READONLY",
        )
    return document


def _require_editable_type(doc_type: str) -> None:
    if doc_type in EDITABLE_TYPES:
        return
    raise ConflictError(
        _ELSEWHERE.get(doc_type, f"Loại tài liệu '{doc_type}' không quản lý ở đây."),
        code="DOCUMENT_TYPE_READONLY",
    )


def _require_can_edit_shared(document: PolicyDocument, actor: User) -> None:
    """Tài liệu dùng chung (`event_id` NULL) áp cho MỌI kỳ — chỉ Quản trị hệ thống được đụng.

    BTC sửa nhầm một dòng ở đây là đổi nội dung của cả những kỳ họ không phụ trách.
    """
    if document.event_id is not None:
        return
    if actor.role != UserRole.SUPER_ADMIN:
        raise AppError(
            "Tài liệu này dùng chung cho mọi kỳ, chỉ Quản trị hệ thống sửa được. "
            "Cần riêng cho kỳ này thì tạo bản sao.",
            code="DOCUMENT_SHARED",
            status_code=403,
        )


def can_edit(document: PolicyDocument, actor: User) -> bool:
    """Frontend dùng để khoá nút sửa/xoá thay vì để người dùng bấm rồi ăn 403."""
    if document.event_id is not None:
        return actor.role in ADMIN_ROLES
    return actor.role == UserRole.SUPER_ADMIN
