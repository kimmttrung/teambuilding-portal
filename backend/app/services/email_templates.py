"""Nội dung email hệ thống gửi cho CBNV.

Vì sao render bằng Python thuần thay vì Jinja2: toàn bộ email của dự án là vài mẫu
ngắn, cùng một khung. Thêm một công cụ template nữa chỉ để nội suy chuỗi là đổi
một dependency lấy không gì cả — và mọi giá trị ở đây đều phải escape HTML tay
(ghi chú của CBNV là dữ liệu người dùng nhập, nhét thẳng vào HTML là lỗ injection).

Mỗi email có cả bản text và bản HTML: một số client nội bộ chặn HTML, và bản text
là thứ lưu vào `email_logs.body_preview` để BTC trả lời "tôi không nhận được mail".

Quy tắc dữ liệu: **không bao giờ đưa số CCCD, ngày sinh, ghi chú sức khoẻ vào email**
(docs/09-security.md §4). Email đi qua hạ tầng ngoài tầm kiểm soát của hệ thống;
khi cần nhắc bổ sung giấy tờ thì chỉ nêu TÊN trường còn thiếu, không nêu giá trị.
"""

from dataclasses import dataclass
from html import escape

from app.core.config import settings
from app.core.timeutils import format_date_only, format_vn

BRAND_COLOR = "#4338ca"


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text: str
    html: str


class UnknownTemplateError(ValueError):
    """Gọi tên template không tồn tại — lỗi lập trình, không phải lỗi người dùng."""


# --- Dữ liệu đầu vào ---


def registration_context(*, event, user, registration, missing_profile_fields=None) -> dict:
    """Gói dữ liệu cho các email về đăng ký.

    Trả về dict thuần (không ORM object) để BackgroundTask dùng được sau khi request
    đã đóng session — chạm vào ORM lúc đó sẽ nổ DetachedInstanceError.
    """
    bus_lines = [
        _bus_line(need)
        for need in sorted(
            registration.bus_needs,
            key=lambda item: item.trip_leg.display_order if item.trip_leg else 0,
        )
        if need.needs_bus
    ]

    return {
        "full_name": user.display_name or user.full_name,
        "event_name": event.name,
        "event_code": event.code,
        "destination": event.destination,
        "start_date": format_date_only(event.start_date),
        "end_date": format_date_only(event.end_date),
        "registration_closes_at": format_vn(event.registration_closes_at),
        "is_participating": registration.is_participating,
        "not_participating_reason": registration.not_participating_reason,
        "shift_name": registration.shift.name if registration.shift else None,
        "bus_lines": bus_lines,
        "wish_note": registration.wish_note,
        "companion_count": registration.companion_count,
        "terms_version": event.terms_version,
        "submitted_at": format_vn(registration.submitted_at),
        "cancelled_at": format_vn(registration.cancelled_at),
        "cancel_reason": registration.cancel_reason,
        "penalty_applied": registration.penalty_applied,
        "missing_profile_fields": list(missing_profile_fields or []),
        "journey_url": f"{settings.APP_PUBLIC_URL}/my-journey",
        "profile_url": f"{settings.APP_PUBLIC_URL}/profile",
        "register_url": f"{settings.APP_PUBLIC_URL}/register-event",
    }


def _bus_line(need) -> str:
    leg = need.trip_leg.name if need.trip_leg else f"Chặng #{need.trip_leg_id}"
    point = need.pickup_point.name if need.pickup_point else None
    return f"{leg} — điểm đón: {point}" if point else leg


# --- Render ---


def render(template: str, context: dict) -> RenderedEmail:
    builder = TEMPLATES.get(template)
    if builder is None:
        raise UnknownTemplateError(f"Không có template email '{template}'.")
    return builder(context)


def _registration_confirmed(context: dict) -> RenderedEmail:
    if context.get("is_participating"):
        subject = f"[{context['event_code']}] Đã nhận đăng ký tham gia của bạn"
        intro = (
            "Ban tổ chức đã nhận đăng ký tham gia Team Building của bạn. "
            "Dưới đây là những gì bạn đã gửi."
        )
    else:
        subject = f"[{context['event_code']}] Đã ghi nhận bạn không tham gia"
        intro = (
            "Ban tổ chức đã ghi nhận bạn không tham gia kỳ Team Building này. "
            "Bạn vẫn đổi ý được trong thời gian còn mở đăng ký."
        )
    return _build(subject, intro, context, kind="confirmed")


def _registration_updated(context: dict) -> RenderedEmail:
    return _build(
        f"[{context['event_code']}] Đăng ký của bạn đã được cập nhật",
        "Đăng ký Team Building của bạn vừa được cập nhật. Đây là thông tin mới nhất — "
        "nếu không phải bạn thay đổi, hãy báo Ban tổ chức ngay.",
        context,
        kind="confirmed",
    )


def _registration_cancelled(context: dict) -> RenderedEmail:
    intro = (
        "Ban tổ chức đã ghi nhận bạn huỷ đăng ký Team Building. "
        "Ban tổ chức sẽ không xếp chuyến bay, xe và phòng cho bạn nữa."
    )
    if context.get("penalty_applied"):
        intro += (
            " Vì huỷ sau hạn đăng ký, hệ thống đã đánh dấu trường hợp của bạn để Ban tổ chức "
            "xem xét chi phí vé máy bay và phòng đã đặt theo quy định chương trình."
        )
    return _build(
        f"[{context['event_code']}] Đã huỷ đăng ký tham gia",
        intro,
        context,
        kind="cancelled",
    )


def reminder_context(*, event, user, missing_fields=None) -> dict:
    """Dữ liệu cho email nhắc việc. Dict thuần, không ORM (xem `registration_context`).

    Chỉ mang TÊN trường còn thiếu, không mang giá trị hồ sơ nào.
    """
    return {
        "full_name": user.display_name or user.full_name,
        "event_name": event.name,
        "event_code": event.code,
        "destination": event.destination,
        "start_date": format_date_only(event.start_date),
        "end_date": format_date_only(event.end_date),
        "registration_closes_at": (
            format_vn(event.registration_closes_at) if event.registration_closes_at else None
        ),
        "missing_fields": list(missing_fields or []),
        "profile_url": f"{settings.APP_PUBLIC_URL}/profile",
        "register_url": f"{settings.APP_PUBLIC_URL}/register-event",
    }


def _event_rows(context: dict) -> list[tuple[str, str]]:
    rows = [("Chương trình", f"{context['event_name']} ({context['event_code']})")]
    if context.get("destination"):
        rows.append(("Điểm đến", context["destination"]))
    rows.append(("Thời gian", f"{context['start_date']} – {context['end_date']}"))
    return rows


def _reminder_missing_documents(context: dict) -> RenderedEmail:
    missing = context.get("missing_fields") or []
    rows = _event_rows(context)
    if missing:
        rows.append(("Hồ sơ còn thiếu", "\n".join(missing)))
    return _compose(
        f"[{context['event_code']}] Nhắc bổ sung thông tin để xuất vé máy bay",
        "Bạn đã xác nhận tham gia Team Building, nhưng hồ sơ còn thiếu thông tin Ban tổ chức "
        "cần để xuất vé máy bay. Chưa bổ sung thì Ban tổ chức không đặt được vé cho bạn.",
        context,
        rows=rows,
        notes=[
            f"Cập nhật hồ sơ tại {context['profile_url']} — chỉ mất khoảng một phút.",
            "Vì an toàn thông tin, email này không chứa dữ liệu cá nhân của bạn. Đừng gửi số "
            "CCCD qua email hay tin nhắn — hãy nhập trực tiếp trên cổng.",
            "Đã bổ sung rồi? Bạn có thể bỏ qua email này.",
        ],
    )


def _reminder_not_registered(context: dict) -> RenderedEmail:
    rows = _event_rows(context)
    if context.get("registration_closes_at"):
        rows.append(("Hạn đăng ký", context["registration_closes_at"]))
    return _compose(
        f"[{context['event_code']}] Bạn chưa gửi đăng ký Team Building",
        "Ban tổ chức chưa nhận được phản hồi của bạn cho kỳ Team Building này. Dù tham gia "
        "hay không, bạn vui lòng xác nhận để Ban tổ chức đặt vé và phòng đúng số người.",
        context,
        rows=rows,
        notes=[
            f"Đăng ký tại {context['register_url']}.",
            'Không tham gia được? Bạn vẫn cần chọn "Không tham gia" để Ban tổ chức không giữ '
            "chỗ cho bạn.",
        ],
    )


def gala_turn_context(
    *, event, user, team_name, layout_name, venue, draw_position, quota, confirmed, turn_ends_at
) -> dict:
    """Dữ liệu email báo Trưởng nhóm tới lượt chọn ghế Gala. Dict thuần, không ORM."""
    return {
        "full_name": user.display_name or user.full_name,
        "event_name": event.name,
        "event_code": event.code,
        "destination": event.destination,
        "start_date": format_date_only(event.start_date),
        "end_date": format_date_only(event.end_date),
        "team_name": team_name,
        "gala_name": layout_name,
        "venue": venue,
        "draw_position": draw_position,
        "quota": quota,
        "confirmed": confirmed,
        "remaining": max(quota - confirmed, 0),
        "turn_ends_at": format_vn(turn_ends_at) if turn_ends_at else None,
        "gala_url": f"{settings.APP_PUBLIC_URL}/gala",
    }


def _gala_turn_started(context: dict) -> RenderedEmail:
    rows = _event_rows(context)
    gala = context["gala_name"] + (f" – {context['venue']}" if context.get("venue") else "")
    rows += [
        ("Gala Dinner", gala),
        ("Team", context["team_name"]),
        ("Lượt", f"#{context['draw_position']}"),
        ("Cần chọn", f"{context['remaining']} ghế (đã chốt {context['confirmed']}/{context['quota']})"),
    ]
    if context.get("turn_ends_at"):
        rows.append(("Hết lượt lúc", f"{context['turn_ends_at']} (giờ Việt Nam)"))
    return _compose(
        f"[{context['event_code']}] Đến lượt team {context['team_name']} chọn ghế Gala Dinner",
        "Team của bạn vừa tới lượt chọn chỗ ngồi Gala Dinner. Bạn là Trưởng nhóm nên là người chọn "
        "ghế cho cả team — vào chọn ngay trước khi hết lượt.",
        context,
        rows=rows,
        notes=[
            f"Chọn ghế tại {context['gala_url']}: bấm ghế trống → Giữ ghế → Xác nhận.",
            "Hết giờ mà chưa xác nhận, lượt tự chuyển cho team kế tiếp và ghế đang giữ được nhả. "
            "Liên hệ Ban tổ chức nếu cần mở lại.",
            'Chốt ghế xong, bấm "Xếp ngẫu nhiên" để xếp nhanh thành viên, rồi đổi chỗ từng người nếu cần.',
        ],
    )


def cancellation_context(
    *, event, cancellation, recipient, kind, event_status_label, released_lines,
    is_team_leader: bool = False,
    reregistered_at: str | None = None,
) -> dict:
    """Dữ liệu các thư về huỷ đăng ký. Dict thuần, không ORM.

    `kind`: "self" | "request" | "withdrawn" | "reregistered" (thư báo BTC) · "requested" | "decided" (thư cho CBNV).
    Chỉ mang tên, mã NV, team, email công ty của người huỷ — không CCCD, SĐT, ngày sinh.
    """
    person = cancellation.user
    review_query = "?status=pending" if kind == "request" else ""
    return {
        "full_name": recipient.display_name or recipient.full_name,
        "event_name": event.name,
        "event_code": event.code,
        "destination": event.destination,
        "start_date": format_date_only(event.start_date),
        "end_date": format_date_only(event.end_date),
        "kind": kind,
        "mode": cancellation.mode,
        "status": cancellation.status,
        "employee_name": person.full_name,
        "employee_code": person.employee_code,
        "employee_email": person.email,
        "team_name": person.team.name if person.team else None,
        "event_status_label": event_status_label,
        "reason": cancellation.reason,
        "requested_at": format_vn(cancellation.requested_at),
        "decided_at": format_vn(cancellation.decided_at) if cancellation.decided_at else None,
        "decision_note": cancellation.decision_note,
        "after_deadline": cancellation.after_deadline,
        "penalty_applied": cancellation.penalty_applied,
        "penalty_note": cancellation.penalty_note,
        "released_lines": list(released_lines),
        "is_team_leader": is_team_leader,
        "reregistered_at": format_vn(reregistered_at) if reregistered_at else None,
        "admin_url": f"{settings.APP_PUBLIC_URL}/admin",
        "review_url": f"{settings.APP_PUBLIC_URL}/admin/cancellations{review_query}",
        "register_url": f"{settings.APP_PUBLIC_URL}/register-event",
        "journey_url": f"{settings.APP_PUBLIC_URL}/my-journey",
    }


def _cancellation_notice_admin(context: dict) -> RenderedEmail:
    kind, name, code = context["kind"], context["employee_name"], context["event_code"]
    if kind == "self":
        subject = f"[{code}] {name} đã tự huỷ đăng ký"
        intro = (
            "Một CBNV vừa tự huỷ đăng ký trước khi Ban tổ chức công bố thông tin. Hệ thống đã huỷ và "
            "giải phóng các chỗ đã xếp cho người này — thư này để Ban tổ chức nắm và xếp lại nếu cần."
        )
    elif kind == "withdrawn":
        subject = f"[{code}] {name} đã rút yêu cầu huỷ đăng ký"
        intro = (
            "CBNV đã rút yêu cầu huỷ đăng ký. Đăng ký và các chỗ đã xếp giữ nguyên, "
            "Ban tổ chức không cần xử lý thêm."
        )
    else:
        subject = f"[{code}] Yêu cầu huỷ đăng ký cần duyệt: {name}"
        intro = (
            "Một CBNV xin huỷ đăng ký sau khi Ban tổ chức đã công bố thông tin. Vé máy bay, xe, phòng "
            "và ghế Gala của người này vẫn được giữ cho tới khi Ban tổ chức duyệt hoặc từ chối."
        )

    person = name + (f" ({context['employee_code']})" if context.get("employee_code") else "")
    rows = _event_rows(context) + [
        ("CBNV", person),
        ("Team", context.get("team_name") or "Chưa gán team"),
        ("Email", context["employee_email"]),
        ("Giai đoạn của kỳ", context["event_status_label"]),
        ("Huỷ lúc" if kind == "self" else "Gửi yêu cầu lúc", context["requested_at"]),
        ("Lý do", context["reason"]),
        (
            "Hạn đăng ký",
            "Đã quá hạn — thuộc diện phí phạt theo quy định"
            if context.get("after_deadline")
            else "Còn trong hạn — không mất phí",
        ),
    ]
    if kind == "self":
        lines = context.get("released_lines") or []
        rows.append(("Đã giải phóng", "\n".join(lines) if lines else "Chưa được xếp chỗ nào"))

    if kind == "request":
        notes = [
            f"Duyệt hoặc từ chối tại {context['review_url']}",
            "Khi duyệt, Ban tổ chức chọn có áp dụng phí phạt hay không; hệ thống gỡ vé máy bay, xe, "
            "phòng, ghế Gala và báo kết quả cho CBNV.",
        ]
        if context.get("is_team_leader"):
            notes.append(
                "Người này đang là Trưởng nhóm: khi duyệt, hệ thống gỡ chức ngay để người đã huỷ không "
                "đổi được ghế Gala của team — chọn Trưởng nhóm mới ngay trong hộp thoại duyệt, hoặc chỉ "
                "định sau trên Dashboard (bảng Đăng ký theo team)."
            )
    else:
        notes = [f"Xem toàn bộ các lần huỷ tại {context['review_url']}"]
        if kind == "self":
            notes.append("Chỗ vừa trống được dùng lại khi chạy lại phân bổ hoặc xếp tay.")
            if context.get("is_team_leader"):
                notes.append(
                    "Người này là Trưởng nhóm nên hệ thống đã gỡ chức ngay — chỉ định Trưởng nhóm mới "
                    f"tại {context['admin_url']} (bảng Đăng ký theo team) để team còn người chọn ghế Gala."
                )
    return _compose(subject, intro, context, rows=rows, notes=notes)


def _registration_reregistered_admin(context: dict) -> RenderedEmail:
    name = context["employee_name"]
    person = name + (f" ({context['employee_code']})" if context.get("employee_code") else "")
    rows = _event_rows(context) + [
        ("CBNV", person),
        ("Team", context.get("team_name") or "Chưa gán team"),
        ("Email", context["employee_email"]),
        ("Giai đoạn hiện tại", context["event_status_label"]),
        ("Huỷ lúc", context.get("decided_at") or context["requested_at"]),
        ("Lý do huỷ trước đó", context["reason"]),
        ("Đăng ký lại lúc", context.get("reregistered_at") or "—"),
    ]
    return _compose(
        f"[{context['event_code']}] {name} đăng ký tham gia lại sau khi huỷ",
        "Một CBNV đã huỷ trước đó vừa đăng ký tham gia lại. Ban tổ chức đã đóng đăng ký nên người này "
        "chưa có chuyến bay, xe, phòng và ghế Gala — cần xếp lại.",
        context,
        rows=rows,
        notes=[
            f"Xem việc cần làm và tiến độ phân bổ tại {context['admin_url']}",
            "Chỗ cũ đã được giải phóng khi huỷ; chức Trưởng nhóm / Trưởng xe (nếu từng có) không tự khôi phục.",
            f"Lịch sử huỷ của người này tại {context['review_url']}",
        ],
    )


def _cancellation_requested(context: dict) -> RenderedEmail:
    rows = _event_rows(context) + [
        ("Gửi yêu cầu lúc", context["requested_at"]),
        ("Lý do", context["reason"]),
    ]
    return _compose(
        f"[{context['event_code']}] Đã gửi yêu cầu huỷ đăng ký",
        "Ban tổ chức đã nhận yêu cầu huỷ đăng ký của bạn. Vì chuyến bay, xe và phòng đã được công bố, "
        "việc huỷ cần Ban tổ chức duyệt.",
        context,
        rows=rows,
        notes=[
            "Trong lúc chờ duyệt, vé máy bay, xe, phòng và ghế Gala của bạn vẫn được giữ.",
            "Theo quy định chương trình, huỷ sau hạn đăng ký có thể phải chịu chi phí vé máy bay và "
            "phòng đã đặt — Ban tổ chức sẽ báo kết quả qua email.",
            f"Đổi ý? Rút yêu cầu tại {context['register_url']} khi Ban tổ chức chưa duyệt.",
        ],
    )


def _cancellation_decided(context: dict) -> RenderedEmail:
    code = context["event_code"]
    if context["status"] != "approved":
        return _compose(
            f"[{code}] Ban tổ chức chưa duyệt yêu cầu huỷ của bạn",
            "Ban tổ chức chưa chấp thuận yêu cầu huỷ đăng ký. Đăng ký của bạn giữ nguyên — chuyến bay, "
            "xe, phòng và ghế Gala vẫn dành cho bạn.",
            context,
            rows=_event_rows(context)
            + [
                ("Lý do bạn gửi", context["reason"]),
                ("Phản hồi của Ban tổ chức", context.get("decision_note") or "—"),
                ("Phản hồi lúc", context.get("decided_at") or "—"),
            ],
            notes=[
                f"Xem lại hành trình tại {context['journey_url']}",
                "Cần trao đổi thêm, vui lòng liên hệ Ban tổ chức.",
            ],
        )

    lead = (
        "Ban tổ chức đã huỷ đăng ký Team Building của bạn theo trao đổi trực tiếp."
        if context.get("mode") == "admin"
        else "Ban tổ chức đã duyệt yêu cầu huỷ đăng ký của bạn."
    )
    if context.get("penalty_applied"):
        penalty = f"Có — {context['penalty_note']}" if context.get("penalty_note") else "Có, theo quy định chương trình"
    else:
        penalty = "Không áp dụng"
    rows = _event_rows(context) + [
        ("Lý do huỷ", context["reason"]),
        ("Xử lý lúc", context.get("decided_at") or "—"),
        ("Phí phạt", penalty),
    ]
    if context.get("decision_note"):
        rows.append(("Ghi chú của Ban tổ chức", context["decision_note"]))
    if context.get("released_lines"):
        rows.append(("Đã giải phóng", "\n".join(context["released_lines"])))
    return _compose(
        f"[{code}] Đăng ký tham gia của bạn đã được huỷ",
        f"{lead} Chuyến bay, xe, phòng và ghế Gala dành cho bạn đã được giải phóng.",
        context,
        rows=rows,
        notes=["Mọi thắc mắc về chi phí, vui lòng liên hệ Ban tổ chức."],
    )


TEMPLATES = {
    "registration_confirmed": _registration_confirmed,
    "registration_updated": _registration_updated,
    "registration_cancelled": _registration_cancelled,
    "reminder_missing_documents": _reminder_missing_documents,
    "reminder_not_registered": _reminder_not_registered,
    "gala_turn_started": _gala_turn_started,
    "registration_reregistered_admin": _registration_reregistered_admin,
    "cancellation_notice_admin": _cancellation_notice_admin,
    "cancellation_requested": _cancellation_requested,
    "cancellation_decided": _cancellation_decided,
}

TEMPLATE_LABELS = {
    "registration_confirmed": "Xác nhận đăng ký",
    "registration_updated": "Cập nhật đăng ký",
    "registration_cancelled": "Huỷ đăng ký",
    "reminder_missing_documents": "Nhắc bổ sung giấy tờ",
    "reminder_not_registered": "Nhắc gửi đăng ký",
    "gala_turn_started": "Đến lượt chọn ghế Gala",
    "cancellation_notice_admin": "Báo BTC có người huỷ",
    "registration_reregistered_admin": "Báo BTC có người đăng ký lại",
    "cancellation_requested": "Đã gửi yêu cầu huỷ",
    "cancellation_decided": "Kết quả huỷ đăng ký",
}


# --- Khung chung ---


def _rows(context: dict, kind: str) -> list[tuple[str, str]]:
    """Các dòng "nhãn: giá trị" của thân email, theo từng loại."""
    rows: list[tuple[str, str]] = [
        ("Chương trình", f"{context['event_name']} ({context['event_code']})"),
    ]
    if context.get("destination"):
        rows.append(("Điểm đến", context["destination"]))
    rows.append(("Thời gian", f"{context['start_date']} – {context['end_date']}"))

    if kind == "cancelled":
        rows.append(("Huỷ lúc", context.get("cancelled_at") or "—"))
        if context.get("cancel_reason"):
            rows.append(("Lý do huỷ", context["cancel_reason"]))
        return rows

    rows.append(("Tham gia", "Có" if context.get("is_participating") else "Không"))

    if context.get("is_participating"):
        rows.append(("Ca đăng ký (nguyện vọng)", context.get("shift_name") or "Chưa chọn"))
        bus_lines = context.get("bus_lines") or []
        rows.append(
            ("Xe của BTC", "\n".join(bus_lines) if bus_lines else "Không đi chặng nào")
        )
        if context.get("companion_count"):
            rows.append(("Người đi cùng", str(context["companion_count"])))
        rows.append(("Quy định đã đồng ý", f"Bản {context.get('terms_version')}"))
    elif context.get("not_participating_reason"):
        rows.append(("Lý do", context["not_participating_reason"]))

    if context.get("wish_note"):
        rows.append(("Mong muốn của bạn", context["wish_note"]))
    rows.append(("Gửi lúc", context.get("submitted_at") or "—"))
    return rows


def _notes(context: dict, kind: str) -> list[str]:
    """Những câu nhắc việc — phần người đọc cần hành động."""
    if kind == "cancelled":
        return [
            f"Đổi ý và muốn tham gia lại? Đăng ký lại tại {context['register_url']} "
            "trong thời gian còn mở đăng ký.",
            "Mọi thắc mắc về chi phí, vui lòng liên hệ Ban tổ chức.",
        ]

    notes = []
    missing = context.get("missing_profile_fields") or []
    if missing:
        notes.append(
            "Hồ sơ của bạn còn thiếu: "
            + ", ".join(missing)
            + f". Ban tổ chức cần đủ thông tin này để xuất vé máy bay — "
            f"bổ sung tại {context['profile_url']}."
        )
    if context.get("is_participating"):
        notes.append(
            "Ca đi là nguyện vọng, chưa phải chỗ đã giữ. Ban tổ chức phân bổ theo số ghế "
            "thực tế của từng chuyến và ưu tiên giữ nguyên team."
        )
        notes.append(
            f"Chuyến bay, xe đưa đón và phòng khách sạn sẽ hiện tại {context['journey_url']} "
            "ngay khi Ban tổ chức công bố."
        )
    notes.append(
        f"Cần sửa đăng ký? Vào {context['register_url']} trước hạn "
        f"{context['registration_closes_at']}."
    )
    return notes


def _build(subject: str, intro: str, context: dict, *, kind: str) -> RenderedEmail:
    return _compose(subject, intro, context, rows=_rows(context, kind), notes=_notes(context, kind))


def _compose(
    subject: str,
    intro: str,
    context: dict,
    *,
    rows: list[tuple[str, str]],
    notes: list[str],
) -> RenderedEmail:
    greeting = f"Chào {context['full_name']},"
    signature = settings.SMTP_FROM_NAME

    return RenderedEmail(
        subject=subject,
        text=_text_body(greeting, intro, rows, notes, signature),
        html=_html_body(subject, greeting, intro, rows, notes, signature),
    )


def _text_body(
    greeting: str, intro: str, rows: list[tuple[str, str]], notes: list[str], signature: str
) -> str:
    lines = [greeting, "", intro, "", "-" * 46]
    for label, value in rows:
        # Giá trị nhiều dòng (danh sách chặng xe) phải thụt vào cho dễ đọc trên client text.
        first, *rest = str(value).split("\n")
        lines.append(f"{label}: {first}")
        lines.extend(f"{' ' * (len(label) + 2)}{item}" for item in rest)
    lines.append("-" * 46)

    if notes:
        lines.append("")
        lines.extend(f"* {note}" for note in notes)

    lines += ["", f"— {signature}", "Email tự động, vui lòng không trả lời thư này."]
    return "\n".join(lines)


def _html_body(
    subject: str,
    greeting: str,
    intro: str,
    rows: list[tuple[str, str]],
    notes: list[str],
    signature: str,
) -> str:
    """HTML cho email: CSS phải inline, layout bằng table.

    Gmail và Outlook bỏ phần lớn `<style>` trong `<head>` và không hỗ trợ flex/grid,
    nên khung này cố tình viết theo lối cũ.
    """
    row_html = "".join(
        f'<tr>'
        f'<td style="padding:6px 12px 6px 0;color:#64748b;font-size:13px;'
        f'white-space:nowrap;vertical-align:top">{escape(str(label))}</td>'
        f'<td style="padding:6px 0;color:#0f172a;font-size:14px;font-weight:600">'
        f'{escape(str(value)).replace(chr(10), "<br>")}</td>'
        f'</tr>'
        for label, value in rows
    )

    notes_html = (
        "<ul style=\"margin:16px 0 0;padding-left:20px;color:#475569;font-size:13px;"
        'line-height:1.6">'
        + "".join(f"<li style=\"margin-bottom:6px\">{_escape_with_links(note)}</li>" for note in notes)
        + "</ul>"
        if notes
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="utf-8"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:24px 12px;background:#f1f5f9;
  font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
    style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden">
    <tr>
      <td style="background:{BRAND_COLOR};padding:18px 24px;color:#ffffff;
        font-size:16px;font-weight:700">Team Building Portal</td>
    </tr>
    <tr>
      <td style="padding:24px">
        <p style="margin:0 0 12px;color:#0f172a;font-size:15px;font-weight:600">
          {escape(greeting)}</p>
        <p style="margin:0 0 20px;color:#334155;font-size:14px;line-height:1.6">
          {escape(intro)}</p>
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%"
          style="border-top:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;padding:8px 0">
          {row_html}
        </table>
        {notes_html}
      </td>
    </tr>
    <tr>
      <td style="padding:16px 24px;background:#f8fafc;color:#94a3b8;font-size:12px;
        line-height:1.6">
        — {escape(signature)}<br>Email tự động, vui lòng không trả lời thư này.
      </td>
    </tr>
  </table>
</body>
</html>"""


def _escape_with_links(text: str) -> str:
    """Escape HTML rồi biến URL thành link bấm được.

    Escape TRƯỚC rồi mới chèn thẻ `<a>`: làm ngược lại thì `escape` sẽ phá luôn thẻ
    vừa chèn, và nội dung do người dùng nhập có thể mang theo HTML.
    """
    safe = escape(text)
    for word in text.split():
        if word.startswith(("http://", "https://")):
            safe_word = escape(word)
            safe = safe.replace(
                safe_word,
                f'<a href="{safe_word}" style="color:{BRAND_COLOR}">{safe_word}</a>',
            )
    return safe
