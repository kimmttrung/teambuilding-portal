"""Gửi một email thử tới địa chỉ bất kỳ, không cần tạo đăng ký thật.

Dùng để kiểm tra cấu hình SMTP (`EMAIL_ENABLED`, `SMTP_*` trong .env) và xem template
hiển thị thế nào trong hộp thư thật.

    py -3.13 scripts/send_test_email.py --to ten.ban@gmail.com
    py -3.13 scripts/send_test_email.py --to ten.ban@gmail.com --template registration_cancelled
    py -3.13 scripts/send_test_email.py --to ten.ban@gmail.com --print-only

Mỗi lần gửi vẫn ghi một dòng vào `email_logs` như email thật, để kiểm tra luôn được
màn hình `GET /admin/email-logs`.
"""

import argparse
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import session_scope  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.services import email_service, email_templates  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s | %(message)s")

DEMO_EVENT = SimpleNamespace(
    code="TB2026",
    name="Team Building 2026 – Phú Quốc",
    destination="Phú Quốc, Kiên Giang",
    start_date="2026-10-15",
    end_date="2026-10-17",
    registration_closes_at="2026-09-25T10:00:00+00:00",
    terms_version="v1",
)


def demo_context(event, to_email: str) -> dict:
    """Dữ liệu mẫu đủ để mọi phần của template hiện ra."""
    user = SimpleNamespace(display_name=None, full_name="Người Thử Nghiệm", email=to_email)
    registration = SimpleNamespace(
        is_participating=True,
        not_participating_reason=None,
        shift=SimpleNamespace(name="Ca 1 – bay sáng"),
        bus_needs=[
            SimpleNamespace(
                needs_bus=True,
                trip_leg_id=1,
                trip_leg=SimpleNamespace(name="HN/HCM → Sân bay", display_order=1),
                pickup_point=SimpleNamespace(name="Toà nhà Keangnam"),
            ),
            SimpleNamespace(
                needs_bus=True,
                trip_leg_id=2,
                trip_leg=SimpleNamespace(name="Sân bay Phú Quốc → Khách sạn", display_order=2),
                pickup_point=None,
            ),
        ],
        wish_note="Đây là email thử cấu hình SMTP, không phải đăng ký thật.",
        companion_count=0,
        submitted_at="2026-09-12T03:00:00+00:00",
        cancelled_at="2026-09-12T04:00:00+00:00",
        cancel_reason="Thử template huỷ đăng ký",
        penalty_applied=False,
    )
    return email_templates.registration_context(
        event=event,
        user=user,
        registration=registration,
        missing_profile_fields=["Số CCCD/Hộ chiếu"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Gửi email thử")
    parser.add_argument("--to", required=True, help="Địa chỉ nhận")
    parser.add_argument(
        "--template",
        default="registration_confirmed",
        choices=sorted(email_templates.TEMPLATES),
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Chỉ in nội dung ra màn hình, không gửi và không ghi email_logs",
    )
    args = parser.parse_args()

    with session_scope() as db:
        # Lấy kỳ đang mở để email mang đúng tên chương trình; chưa có thì dùng dữ liệu mẫu.
        event = db.scalar(select(Event).where(Event.is_active.is_(True))) or DEMO_EVENT
        context = demo_context(event, args.to)

        if args.print_only:
            rendered = email_templates.render(args.template, context)
            print(f"SUBJECT: {rendered.subject}\n")
            print(rendered.text)
            return 0

        print(
            f"EMAIL_ENABLED={settings.EMAIL_ENABLED} "
            f"SMTP={settings.SMTP_HOST}:{settings.SMTP_PORT} "
            f"STARTTLS={settings.SMTP_STARTTLS} FROM={settings.SMTP_FROM_EMAIL}"
        )
        entry = email_service.send(
            db,
            template=args.template,
            to_email=args.to,
            context=context,
            related_type="test",
        )
        if entry is None:
            print("Không gửi: thiếu địa chỉ nhận.")
            return 1

        # Đọc ra biến thường NGAY trong session: ra khỏi `with` là session đóng,
        # chạm vào thuộc tính ORM sẽ ném DetachedInstanceError.
        result = {
            "id": entry.id,
            "status": entry.status,
            "sent_at": entry.sent_at,
            "error_message": entry.error_message,
        }

    print(f"\nemail_logs #{result['id']}: status={result['status']} sent_at={result['sent_at']}")
    if result["error_message"]:
        print(f"Ghi chú / lỗi: {result['error_message']}")
    if not settings.EMAIL_ENABLED:
        print(
            "\nĐang ở chế độ dev (EMAIL_ENABLED=false) nên chưa gửi thật — nội dung nằm ở log "
            "phía trên. Đặt EMAIL_ENABLED=true và khai SMTP_* trong .env để gửi thật."
        )
    return 0 if result["status"] != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
