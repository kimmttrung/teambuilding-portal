"""Tài liệu chương trình (FAQ / hướng dẫn) — nguồn kiến thức của chatbot (docs/13 task 4)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.content import PolicyDocument
from app.models.enums import EventStatus, PolicyDocType, UserRole
from app.models.event import Event

URL = "/api/v1/admin/documents"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    event = Event(
        code="TB2026", name="Team Building 2026", start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN, terms_version="v1",
        terms_content="# Quy định", is_active=True,
    )
    other = Event(
        code="TB2027", name="Team Building 2027", start_date="2027-04-16", end_date="2027-04-18",
        status=EventStatus.REGISTRATION_OPEN, terms_version="v1", is_active=False,
    )
    db.add_all([event, other])
    db.flush()

    make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Ban Tổ Chức")
    make_user(email="sa@company.vn", role=UserRole.SUPER_ADMIN, full_name="Quản Trị")
    make_user(email="nv@company.vn", full_name="Nguyễn Văn A")

    faq = PolicyDocument(
        event_id=event.id, doc_type=PolicyDocType.FAQ, title="Câu hỏi thường gặp",
        content="Mang theo CCCD.", version="v1", is_indexed=True, updated_at="2026-09-01T00:00:00+00:00",
    )
    shared = PolicyDocument(
        event_id=None, doc_type=PolicyDocType.GUIDE, title="Hướng dẫn dùng cổng",
        content="Đăng nhập bằng email công ty.", version="v1", is_indexed=True,
        updated_at="2026-09-01T00:00:00+00:00",
    )
    terms_doc = PolicyDocument(
        event_id=event.id, doc_type=PolicyDocType.TERMS, title="Quy định", content="# Quy định",
        version="v1", is_indexed=True, updated_at="2026-09-01T00:00:00+00:00",
    )
    foreign = PolicyDocument(
        event_id=other.id, doc_type=PolicyDocType.FAQ, title="FAQ kỳ Đà Nẵng",
        content="Riêng kỳ 2027.", version="v1", is_indexed=True, updated_at="2026-09-01T00:00:00+00:00",
    )
    db.add_all([faq, shared, terms_doc, foreign])
    db.commit()
    return {
        "event": event.id, "other": other.id,
        "faq": faq.id, "shared": shared.id, "terms": terms_doc.id, "foreign": foreign.id,
    }


def error_code(response) -> str:
    return response.json()["error"]["code"]


def test_list_shows_event_and_shared_docs_but_never_terms_or_other_events(
    client: TestClient, auth_headers, world
):
    """Quy định có nguồn riêng (`events.terms_content`) nên không được hiện ở đây —
    hai chỗ sửa cùng một nội dung là chắc chắn lệch nhau."""
    rows = client.get(URL, headers=auth_headers("btc@company.vn")).json()
    assert [row["id"] for row in rows] == [world["faq"], world["shared"]]

    shared = next(row for row in rows if row["id"] == world["shared"])
    assert shared["is_shared"] is True
    assert shared["can_edit"] is False, "BTC không sửa được tài liệu dùng chung"
    assert next(row for row in rows if row["id"] == world["faq"])["can_edit"] is True


def test_create_and_update_marks_knowledge_base_stale(
    client: TestClient, auth_headers, world, db: Session
):
    """Sửa tài liệu xong mà `is_indexed` vẫn true thì BTC tưởng Tibi đã đọc bản mới."""
    admin = auth_headers("btc@company.vn")

    created = client.post(
        URL, headers=admin,
        json={"doc_type": "guide", "title": "Hướng dẫn đổi chuyến", "content": "Liên hệ BTC."},
    )
    assert created.status_code == 201, created.text
    assert created.json()["is_indexed"] is False
    assert created.json()["is_shared"] is False

    updated = client.patch(
        f"{URL}/{world['faq']}", headers=admin, json={"content": "Mang theo CCCD và vé."}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["is_indexed"] is False, "nội dung đổi thì vector store đã cũ"

    # Audit không được chứa cả nội dung tài liệu, chỉ độ dài.
    entry = db.query(AuditLog).filter(AuditLog.action == "document.updated").one()
    assert "content_length" in entry.after_data
    assert "Mang theo CCCD và vé" not in (entry.after_data or "")


def test_terms_and_foreign_event_docs_are_not_reachable(client: TestClient, auth_headers, world):
    admin = auth_headers("btc@company.vn")

    blocked = client.patch(f"{URL}/{world['terms']}", headers=admin, json={"title": "Đổi tên"})
    assert blocked.status_code == 409
    assert error_code(blocked) == "DOCUMENT_TYPE_READONLY"

    assert client.post(
        URL, headers=admin, json={"doc_type": "terms", "title": "Quy định 2", "content": "x"}
    ).status_code == 409

    other_event = client.patch(f"{URL}/{world['foreign']}", headers=admin, json={"title": "Đổi"})
    assert other_event.status_code == 404
    assert error_code(other_event) == "DOCUMENT_NOT_FOUND"


def test_shared_doc_is_editable_by_super_admin_only(client: TestClient, auth_headers, world):
    """Tài liệu dùng chung áp cho mọi kỳ — BTC sửa nhầm là đổi nội dung của cả kỳ họ không phụ trách."""
    denied = client.patch(
        f"{URL}/{world['shared']}", headers=auth_headers("btc@company.vn"), json={"title": "Đổi"}
    )
    assert denied.status_code == 403
    assert error_code(denied) == "DOCUMENT_SHARED"
    assert client.delete(
        f"{URL}/{world['shared']}", headers=auth_headers("btc@company.vn")
    ).status_code == 403

    allowed = client.patch(
        f"{URL}/{world['shared']}", headers=auth_headers("sa@company.vn"), json={"title": "Hướng dẫn mới"}
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["can_edit"] is True


def test_delete_removes_the_document_and_employees_cannot_reach_the_api(
    client: TestClient, auth_headers, world, db: Session
):
    admin = auth_headers("btc@company.vn")
    assert client.delete(f"{URL}/{world['faq']}", headers=admin).status_code == 204
    assert db.get(PolicyDocument, world["faq"]) is None
    assert db.query(AuditLog).filter(AuditLog.action == "document.deleted").count() == 1

    assert client.get(URL, headers=auth_headers("nv@company.vn")).status_code == 403
    assert client.post(
        URL, headers=auth_headers("nv@company.vn"),
        json={"doc_type": "faq", "title": "x", "content": "y"},
    ).status_code == 403


def test_documents_follow_the_selected_event(client: TestClient, auth_headers, world):
    """Đổi kỳ thì danh sách tài liệu phải đổi theo — cùng dependency với mọi endpoint khác."""
    admin = dict(auth_headers("btc@company.vn"))
    on_other = client.get(URL, headers={**admin, "X-Event-Id": str(world["other"])}).json()
    assert [row["id"] for row in on_other] == [world["foreign"], world["shared"]]
