"""Mẫu Excel có dữ liệu minh hoạ, hướng dẫn và danh mục mã để BTC điền trực tiếp."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accommodation import Hotel, Room
from app.models.org import Department, Team, WorkLocation
from app.services.excel import Sheet, build_workbook


def users_template(db: Session) -> bytes:
    references = []
    examples = []
    for model, label, fallback in (
        (Team, "Team", "TEAM_IT"),
        (Department, "Phòng ban", "PB_IT"),
        (WorkLocation, "Nơi làm việc", "HN"),
    ):
        records = db.scalars(select(model).order_by(model.code)).all()
        examples.append(records[0].code if records else fallback)
        references.extend([[label, item.code, item.name] for item in records])
    headers = [
        "Mã NV",
        "Họ tên",
        "Email",
        "Giới tính",
        "SĐT",
        "Team",
        "Phòng ban",
        "Nơi làm việc",
        "Chức danh",
        "Ngày vào làm",
        "Vai trò",
        "Ngày sinh",
        "Số CCCD/Hộ chiếu",
    ]
    rows = [
        [
            "NV_MAU001",
            "Nguyễn Văn An",
            "nv.mau001@company.vn",
            "Nam",
            "0912345678",
            *examples,
            "Kỹ sư phần mềm",
            "01/03/2020",
            "CBNV",
            "20/03/1995",
            "001095012345",
        ],
        [
            "NV_MAU002",
            "Trần Thị Bình",
            "nv.mau002@company.vn",
            "Nữ",
            "0987654321",
            *examples,
            "Trưởng nhóm",
            "15/06/2019",
            "Trưởng nhóm",
            "12/07/1994",
            "001094012346",
        ],
    ]
    guide = [
        [
            "Cách dùng",
            "Thay hoặc xoá các dòng ví dụ ở sheet đầu tiên. Giữ nguyên tên cột; mỗi "
            "dòng là một CBNV.",
        ],
        [
            "Bắt buộc",
            "Mã NV, Họ tên, Email. Mã NV dài 2–32 ký tự: chữ, số, dấu chấm, gạch ngang, gạch dưới.",
        ],
        [
            "Team / Phòng ban / Nơi làm việc",
            "Dùng mã hoặc tên đã có trong sheet Danh mục. Mã ví dụ chưa có thì thay hoặc để trống.",
        ],
        ["Giới tính", "Nam / Nữ / Khác."],
        ["Vai trò", "CBNV / Trưởng nhóm; không cấp quyền BTC qua import."],
        ["Ngày vào làm / Ngày sinh", "Dùng dd/mm/yyyy, yyyy-mm-dd hoặc ô ngày Excel."],
        ["SĐT / CCCD", "Giữ định dạng Text để không mất số 0 đầu."],
        ["Cập nhật", "Khớp tài khoản theo Mã NV, sau đó Email. Ô trống giữ nguyên dữ liệu cũ."],
        [
            "Email tài khoản mới",
            "Chỉ khi ghi thật: hệ thống gửi email đăng nhập cho tài khoản mới. Kiểm "
            "tra file không gửi email.",
        ],
        [
            "Kiểm tra",
            "Tối đa 2000 dòng. Kiểm tra file trước khi ghi; còn lỗi thì không ghi dòng nào.",
        ],
    ]
    return build_workbook(
        [
            Sheet("CBNV", headers, rows),
            Sheet("Hướng dẫn", ["Mục", "Nội dung"], guide, wrap_text=True),
            Sheet("Danh mục", ["Loại", "Mã", "Tên"], references),
        ]
    )


def rooms_template(db: Session, *, event_id: int) -> bytes:
    rooms = db.execute(
        select(Room, Hotel)
        .join(Hotel)
        .where(Hotel.event_id == event_id)
        .order_by(Hotel.name, Room.room_number)
    ).all()
    sample_room, sample_hotel = (
        (rooms[0][0].room_number, rooms[0][1].name) if rooms else ("1204", "Khách sạn mẫu")
    )
    guide = [
        [
            "Cách dùng",
            "Thay hoặc xoá các dòng ví dụ ở sheet đầu tiên. Giữ nguyên tên cột; mỗi "
            "dòng là một người.",
        ],
        [
            "Bắt buộc",
            "Số phòng và Mã NV hoặc Email. Các ví dụ NV_MAU001/NV_MAU002 cần thay "
            "bằng người đã đăng ký tham gia.",
        ],
        [
            "Khách sạn / Số phòng",
            "Chọn phòng đã có trong sheet Danh mục phòng. Khi nhiều khách sạn có "
            "cùng số phòng, phải ghi tên khách sạn.",
        ],
        [
            "Mã NV / Email",
            "Dùng mã hoặc email của người đã gửi đăng ký tham gia trong kỳ đang chọn.",
        ],
        ["Trưởng phòng", "x / 1 / có / true = trưởng phòng; để trống = không."],
        [
            "Chuyển phòng",
            "Người đã có phòng chỉ được chuyển khi bật tuỳ chọn thay phân phòng hiện "
            "có trên giao diện.",
        ],
        ["Điều kiện", "Kiểm tra giới tính, sức chứa và trưởng phòng như khi xếp tay."],
        ["Kiểm tra", "Tối đa 2000 dòng. Kiểm tra trước khi ghi; còn lỗi thì không ghi dòng nào."],
    ]
    return build_workbook(
        [
            Sheet(
                "Phân phòng",
                ["Số phòng", "Mã NV", "Email", "Khách sạn", "Trưởng phòng"],
                [
                    [sample_room, "NV_MAU001", "nv.mau001@company.vn", sample_hotel, "x"],
                    [sample_room, "NV_MAU002", "nv.mau002@company.vn", sample_hotel, ""],
                ],
            ),
            Sheet("Hướng dẫn", ["Mục", "Nội dung"], guide, wrap_text=True),
            Sheet(
                "Danh mục phòng",
                ["Khách sạn", "Số phòng", "Sức chứa", "Giới tính"],
                [
                    [hotel.name, room.room_number, room.capacity, room.gender_policy]
                    for room, hotel in rooms
                ],
            ),
        ]
    )
