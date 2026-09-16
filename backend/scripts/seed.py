"""Nạp dữ liệu mẫu cho môi trường dev/demo.

    python scripts/seed.py            # tạo mới (báo lỗi nếu đã có dữ liệu)
    python scripts/seed.py --reset    # xoá sạch rồi tạo lại

Dữ liệu cố ý "khó" để demo được thuật toán ở bước sau:
  - Team lệch nhau (26 người tới 7 người) -> có team phải tách chuyến
  - Nguyện vọng dồn vào Ca 2 nhiều hơn số ghế Ca 2 -> có người không được đúng ca
  - 10% CBNV thiếu CCCD -> hiện cảnh báo MISSING_ID_CARD trên dashboard
  - Tổng slot chỉ nhiều hơn nhu cầu một chút -> thấy rõ chuyến gần đầy

Random dùng seed cố định nên chạy lại luôn ra cùng dữ liệu.
"""

import argparse
import random
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import session_scope  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.core.timeutils import VN_TZ, to_iso, utcnow_iso  # noqa: E402
from app.models import (  # noqa: E402
    Announcement,
    Base,
    Bus,
    Consent,
    Department,
    Event,
    EventSetting,
    Flight,
    GalaLayout,
    GalaSeat,
    GalaTable,
    Hotel,
    ItineraryItem,
    PickupPoint,
    PolicyDocument,
    Registration,
    RegistrationBusNeed,
    Room,
    Shift,
    Team,
    TripLeg,
    User,
    WorkLocation,
)
from app.models.enums import (  # noqa: E402
    AnnouncementSeverity,
    FlightDirection,
    Gender,
    PolicyDocType,
    RegistrationStatus,
    RoomGenderPolicy,
    UserRole,
)

EVENT_CODE = "TB2026"
# Kỳ thứ hai để thử chạy song song (docs/13 task 6). Không phải kỳ mặc định.
SECOND_EVENT_CODE = "TB2027"
DEMO_PASSWORD = "Matkhau123"
ADMIN_PASSWORD = "Admin12345"
RANDOM_SEED = 20261015

rng = random.Random(RANDOM_SEED)


def vn_time(day: str, hhmm: str) -> str:
    """('2026-10-15', '06:30') giờ Việt Nam -> ISO UTC '2026-10-14T23:30:00+00:00'.

    DB lưu UTC. Viết thẳng '2026-10-15T06:30:00+00:00' là lưu 06:30 UTC = 13:30 giờ VN — lệch 7 tiếng
    trên My Journey, file Excel và câu trả lời của chatbot.
    """
    return to_iso(datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=VN_TZ))

# --- Dữ liệu nguồn để sinh tên tiếng Việt ---

HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Ngô", "Dương", "Lý"]
DEM_NAM = ["Văn", "Hữu", "Đức", "Quang", "Minh", "Thanh", "Công", "Xuân"]
DEM_NU = ["Thị", "Thu", "Ngọc", "Thanh", "Minh", "Phương", "Kim"]
TEN_NAM = ["An", "Bách", "Cường", "Dũng", "Đạt", "Hải", "Hùng", "Khánh", "Long", "Nam",
           "Phong", "Quân", "Sơn", "Tuấn", "Trung", "Việt", "Vinh", "Thắng"]
TEN_NU = ["Anh", "Chi", "Dung", "Giang", "Hà", "Hoa", "Hương", "Lan", "Linh", "Mai",
          "Ngân", "Nhung", "Oanh", "Phương", "Quỳnh", "Thảo", "Trang", "Yến"]

SHIRT_SIZES = ["S", "M", "L", "XL", "XXL"]
DIETARY = [None] * 12 + ["Ăn chay", "Dị ứng hải sản", "Không ăn được đồ cay"]

DEPARTMENTS = [
    ("KD", "Khối Kinh doanh"),
    ("VH", "Khối Vận hành"),
    ("CN", "Khối Công nghệ"),
    ("HT", "Khối Hỗ trợ"),
]

# (mã team, tên, mã phòng ban, số người, địa điểm, màu)
TEAMS = [
    ("SALES-HN", "Kinh doanh Hà Nội", "KD", 26, "HN", "#2563eb"),
    ("SALES-HCM", "Kinh doanh TP.HCM", "KD", 20, "HCM", "#0891b2"),
    ("OPS-HN", "Vận hành Hà Nội", "VH", 18, "HN", "#059669"),
    ("IT-HN", "Công nghệ Hà Nội", "CN", 15, "HN", "#7c3aed"),
    ("IT-HCM", "Công nghệ TP.HCM", "CN", 14, "HCM", "#db2777"),
    ("MKT", "Marketing", "HT", 11, "HN", "#d97706"),
    ("HR", "Nhân sự", "HT", 9, "HN", "#be123c"),
    ("FIN", "Tài chính Kế toán", "HT", 7, "HN", "#475569"),
]

TRIP_LEGS = [
    ("CITY_TO_AIRPORT", "HN/HCM → Sân bay", FlightDirection.OUTBOUND, True, 1),
    ("AIRPORT_TO_HOTEL", "Sân bay Phú Quốc → Khách sạn", FlightDirection.OUTBOUND, True, 2),
    ("HOTEL_TO_AIRPORT", "Khách sạn → Sân bay Phú Quốc", FlightDirection.RETURN, True, 3),
    ("AIRPORT_TO_CITY", "Sân bay → HN/HCM", FlightDirection.RETURN, True, 4),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Nạp dữ liệu mẫu")
    parser.add_argument("--reset", action="store_true", help="Xoá toàn bộ dữ liệu trước khi nạp")
    parser.add_argument(
        "--registration-rate",
        type=float,
        default=1.0,
        help="Tỉ lệ CBNV đã gửi đăng ký (0–1). Mặc định 1 = mọi người. "
        "Demo luồng CBNV tự đăng ký + email nhắc thì dùng 0.7.",
    )
    parser.add_argument(
        "--second-event",
        action="store_true",
        help="Nạp thêm kỳ TB2027 – Đà Nẵng để thử nhiều kỳ song song (docs/13 task 6)",
    )
    args = parser.parse_args()
    if not 0 <= args.registration_rate <= 1:
        parser.error("--registration-rate phải nằm trong khoảng 0 đến 1")

    with session_scope() as db:
        if args.reset:
            wipe(db)
        elif db.scalar(select(Event).where(Event.code == EVENT_CODE)):
            # DB đang có dữ liệu thật: `--second-event` chỉ THÊM kỳ phụ, không nạp lại gì khác.
            if args.second_event:
                return add_second_event_to_existing_db(db)
            print(f"Đã có kỳ {EVENT_CODE} trong database. Dùng --reset để nạp lại từ đầu,")
            print("hoặc --second-event để thêm kỳ TB2027 mà giữ nguyên dữ liệu hiện có.")
            return 1

        event = create_event(db)
        departments = create_departments(db)
        locations = create_work_locations(db)
        shifts = create_shifts(db, event)
        legs = create_trip_legs(db, event)
        pickups = create_pickup_points(db, event, legs, locations)
        teams = create_teams(db, departments)
        users = create_users(db, teams, departments, locations)
        create_admins(db, departments, locations)
        flights = create_flights(db, event, shifts)
        create_buses(db, event, legs, pickups, flights, users)
        create_hotel_and_rooms(db, event)
        create_gala(db, event)
        create_itinerary(db, event)
        create_content(db, event)
        registrations = create_registrations(
            db, event, users, shifts, legs, pickups, registration_rate=args.registration_rate
        )
        if args.second_event:
            create_second_event(db, users, locations)

        db.flush()
        print_summary(db, teams, users, registrations, flights)
    return 0


# --- Xoá dữ liệu ---


def wipe(db: Session) -> None:
    """Xoá sạch mọi bảng nghiệp vụ, giữ lại alembic_version."""
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.flush()
    print("Đã xoá dữ liệu cũ.")


# --- Master data ---


def create_event(db: Session) -> Event:
    event = Event(
        code=EVENT_CODE,
        name="Team Building 2026 – Phú Quốc",
        destination="Phú Quốc, Kiên Giang",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status="registration_open",
        registration_opens_at="2026-09-01T00:00:00+00:00",
        # 17h00 giờ Việt Nam = 10:00 UTC. Ghi 17:00 UTC là hạn thật thành 00:00 ngày 26/09,
        # lệch với quy định và với email nhắc hạn gửi cho CBNV.
        registration_closes_at="2026-09-25T10:00:00+00:00",
        terms_version="v1",
        terms_content=TERMS_MARKDOWN,
        is_active=True,
    )
    db.add(event)
    db.flush()

    from app.models import DEFAULT_EVENT_SETTINGS

    for key, (value, description) in DEFAULT_EVENT_SETTINGS.items():
        db.add(EventSetting(event_id=event.id, key=key, value=value, description=description))
    return event


def create_second_event(
    db: Session,
    users: list[User],
    locations: dict[str, WorkLocation],
    *,
    registration_rate: float = 0.55,
) -> Event:
    """Kỳ thứ hai chạy song song với TB2026 — để thử `X-Event-Id` (docs/13 task 6).

    Dữ liệu riêng hoàn toàn (ca, chặng, điểm đón, chuyến bay, khách sạn, Gala, lịch trình, đăng ký)
    nên đổi kỳ trên thanh chọn là mọi màn hình phải đổi theo. Dùng chung CBNV / team / phòng ban vì
    đó là dữ liệu công ty, không gắn kỳ.

    KHÔNG đặt `is_active`: TB2026 vẫn là kỳ mặc định, client không gửi header vẫn thấy y như cũ.
    """
    event = Event(
        code=SECOND_EVENT_CODE,
        name="Team Building 2027 – Đà Nẵng",
        destination="Đà Nẵng",
        start_date="2027-04-16",
        end_date="2027-04-18",
        status="registration_open",
        registration_opens_at="2027-03-01T00:00:00+00:00",
        registration_closes_at="2027-03-26T10:00:00+00:00",
        terms_version="v1",
        terms_content=TERMS_MARKDOWN,
        is_active=False,
    )
    db.add(event)
    db.flush()

    from app.models import DEFAULT_EVENT_SETTINGS

    for key, (value, description) in DEFAULT_EVENT_SETTINGS.items():
        db.add(EventSetting(event_id=event.id, key=key, value=value, description=description))

    shifts = {
        row.code: row
        for row in [
            Shift(event_id=event.id, code="CA1", name="Ca 1 – bay sáng",
                  description="Khởi hành buổi sáng.", earliest_departure="06:00", display_order=1),
            Shift(event_id=event.id, code="CA2", name="Ca 2 – bay chiều",
                  description="Dành cho bộ phận trực đến hết giờ giao dịch.",
                  earliest_departure="17:00", display_order=2),
        ]
    }
    db.add_all(list(shifts.values()))
    db.flush()

    legs = {}
    for code, name, direction, order in [
        ("CITY_TO_AIRPORT", "HN/HCM → Sân bay", FlightDirection.OUTBOUND, 1),
        ("AIRPORT_TO_HOTEL", "Sân bay Đà Nẵng → Khách sạn", FlightDirection.OUTBOUND, 2),
        ("HOTEL_TO_AIRPORT", "Khách sạn → Sân bay Đà Nẵng", FlightDirection.RETURN, 3),
        ("AIRPORT_TO_CITY", "Sân bay → HN/HCM", FlightDirection.RETURN, 4),
    ]:
        leg = TripLeg(
            event_id=event.id, code=code, name=name, direction=direction,
            is_airport_linked=True, display_order=order,
            leg_date="2027-04-16" if direction == FlightDirection.OUTBOUND else "2027-04-18",
        )
        db.add(leg)
        legs[code] = leg
    db.flush()

    pickups = {}
    for order, (key, name, address, location_code) in enumerate([
        ("HN-KEANGNAM", "Toà nhà Keangnam", "Phạm Hùng, Nam Từ Liêm, Hà Nội", "HN"),
        ("HN-HOANKIEM", "Trụ sở Hoàn Kiếm", "Lý Thường Kiệt, Hoàn Kiếm, Hà Nội", "HN"),
        ("HCM-BITEXCO", "Toà nhà Bitexco", "Hải Triều, Quận 1, TP.HCM", "HCM"),
    ]):
        point = PickupPoint(
            event_id=event.id, trip_leg_id=legs["CITY_TO_AIRPORT"].id,
            work_location_id=locations[location_code].id,
            name=name, address=address, display_order=order,
        )
        db.add(point)
        pickups[key] = point
    db.flush()

    for code, direction, shift_code, departure, arrival, dep_at, arr_at, capacity in [
        ("VN0161", FlightDirection.OUTBOUND, "CA1", "HAN", "DAD", "07:00", "08:20", 70),
        ("VN0175", FlightDirection.OUTBOUND, "CA2", "HAN", "DAD", "18:00", "19:20", 60),
        ("VN0162", FlightDirection.RETURN, "CA1", "DAD", "HAN", "14:00", "15:20", 70),
        ("VN0176", FlightDirection.RETURN, "CA2", "DAD", "HAN", "20:00", "21:20", 60),
    ]:
        day = "2027-04-16" if direction == FlightDirection.OUTBOUND else "2027-04-18"
        db.add(Flight(
            event_id=event.id, flight_code=code, airline="Vietnam Airlines", direction=direction,
            shift_id=shifts[shift_code].id, departure_airport=departure, arrival_airport=arrival,
            departure_time=vn_time(day, dep_at), arrival_time=vn_time(day, arr_at),
            capacity=capacity, reserved_slots=2,
        ))

    hotel = Hotel(
        event_id=event.id,
        name="Furama Resort Đà Nẵng",
        address="103–105 Võ Nguyên Giáp, Ngũ Hành Sơn, Đà Nẵng",
        phone="0236 3847 333",
        check_in_at="2027-04-16T07:00:00+00:00",
        check_out_at="2027-04-18T05:00:00+00:00",
        map_url="https://maps.google.com/?q=Furama+Resort+Da+Nang",
    )
    db.add(hotel)
    db.flush()
    for floor in range(3, 8):
        for number in range(1, 11):
            db.add(Room(
                hotel_id=hotel.id,
                room_number=f"{floor}{number:02d}",
                floor=floor,
                room_type="twin",
                capacity=2,
                gender_policy=RoomGenderPolicy.ANY,
            ))

    layout = GalaLayout(
        event_id=event.id,
        name="Gala Dinner – Đêm hội Đà Nẵng",
        venue="Sảnh Ariyana, Furama Resort",
        starts_at=vn_time("2027-04-17", "18:30"),
        stage_position="top",
        grid_width=12,
        grid_height=8,
    )
    db.add(layout)
    db.flush()
    for index in range(12):
        table = GalaTable(
            layout_id=layout.id, table_code=f"B{index + 1:02d}", seat_count=10,
            pos_x=(index % 4) * 3, pos_y=(index // 4) * 2,
        )
        table.seats = [GalaSeat(seat_number=number) for number in range(1, 11)]
        db.add(table)

    db.add_all([
        ItineraryItem(
            event_id=event.id, day_date=day, start_time=start, end_time=end,
            title=title, location=location, audience=audience, display_order=order,
        )
        for order, (day, start, end, title, location, audience) in enumerate([
            ("2027-04-16", "04:30", "05:00", "Tập trung tại điểm đón", "Theo xe đã phân công", "CA1"),
            ("2027-04-16", "07:00", "08:20", "Chuyến bay HAN – DAD", "Sân bay Nội Bài", "CA1"),
            ("2027-04-16", "09:30", "11:00", "Nhận phòng khách sạn", "Furama Resort", "all"),
            ("2027-04-16", "15:00", "17:30", "Team Building bãi biển", "Bãi Mỹ Khê", "all"),
            ("2027-04-17", "09:00", "11:30", "Trò chơi vận động theo Team", "Sân trung tâm", "all"),
            ("2027-04-17", "14:00", "17:00", "Tự do / Tour Bà Nà Hills", "Cáp treo Bà Nà", "all"),
            ("2027-04-17", "18:30", "22:00", "Gala Dinner & Vinh danh", "Sảnh Ariyana", "all"),
            ("2027-04-18", "07:00", "08:30", "Ăn sáng và trả phòng", "Furama Resort", "all"),
            ("2027-04-18", "14:00", "15:20", "Chuyến bay DAD – HAN", "Sân bay Đà Nẵng", "CA1"),
        ])
    ])

    _register_for_second_event(
        db, event, users, shifts, legs, pickups, registration_rate=registration_rate
    )
    db.flush()
    return event


def _register_for_second_event(
    db: Session,
    event: Event,
    users: list[User],
    shifts: dict[str, Shift],
    legs: dict[str, TripLeg],
    pickups: dict[str, PickupPoint],
    *,
    registration_rate: float,
) -> None:
    """Đăng ký cho kỳ phụ, suy địa điểm từ `user.work_location` chứ không theo thứ tự danh sách.

    `create_registrations` ghép user với cấu hình team **theo vị trí trong list**, chỉ đúng ngay sau
    khi vừa tạo user. Chạy trên DB có sẵn (đã thêm/xoá tài khoản) thì cách ghép đó lệch, nên ở đây
    đọc thẳng nơi làm việc đã lưu của từng người.
    """
    pickup_by_location = {
        "HN": [pickups["HN-KEANGNAM"], pickups["HN-HOANKIEM"]],
        "HCM": [pickups["HCM-BITEXCO"]],
    }
    for user in users:
        if user.role in ("admin", "super_admin") or not user.is_active:
            continue
        if registration_rate < 1 and rng.random() >= registration_rate:
            continue
        code = user.work_location.code if user.work_location else "HN"
        points = pickup_by_location.get(code) or pickup_by_location["HN"]

        participating = rng.random() < 0.85
        shift = shifts["CA2"] if rng.random() < 0.62 else shifts["CA1"]
        registration = Registration(
            event_id=event.id,
            user_id=user.id,
            is_participating=participating,
            not_participating_reason=None if participating else "Bận việc gia đình",
            shift_id=shift.id if participating else None,
            departure_location_id=user.work_location_id,
            wish_note=rng.choice(WISH_NOTES) if participating and rng.random() < 0.3 else None,
            status=RegistrationStatus.SUBMITTED,
            submitted_at=utcnow_iso(),
        )
        db.add(registration)
        db.flush()
        if not participating:
            continue

        db.add(Consent(
            user_id=user.id, event_id=event.id, terms_version=event.terms_version,
            agreed_at=utcnow_iso(), ip_address="10.0.0.1",
        ))
        pickup = rng.choice(points)
        for leg in legs.values():
            needs_bus = rng.random() < 0.8
            db.add(RegistrationBusNeed(
                registration_id=registration.id,
                trip_leg_id=leg.id,
                needs_bus=needs_bus,
                pickup_point_id=pickup.id if needs_bus and leg.code == "CITY_TO_AIRPORT" else None,
            ))
    db.flush()


def add_second_event_to_existing_db(db: Session) -> int:
    """Thêm kỳ TB2027 vào database đã có dữ liệu, KHÔNG đụng gì tới kỳ cũ.

    Dùng khi đang chạy thật mà muốn thử chọn kỳ: `scripts/seed.py --second-event` (không `--reset`).
    Chạy lại lần nữa không tạo trùng.
    """
    if db.scalar(select(Event).where(Event.code == SECOND_EVENT_CODE)):
        print(f"Đã có kỳ {SECOND_EVENT_CODE} rồi, không tạo thêm.")
        return 0

    locations = {row.code: row for row in db.scalars(select(WorkLocation))}
    if not locations:
        print("Database chưa có nơi làm việc nào — chạy seed đầy đủ trước.")
        return 1
    users = list(db.scalars(select(User).order_by(User.id)))

    event = create_second_event(db, users, locations)
    db.flush()
    joined = db.scalar(
        select(func.count(Registration.id)).where(
            Registration.event_id == event.id, Registration.is_participating.is_(True)
        )
    )
    print(f"Đã thêm kỳ {event.code} – {event.name} (id={event.id}).")
    print(f"  {joined} người xác nhận tham gia · kỳ mặc định vẫn là {EVENT_CODE}.")
    print('  Đăng nhập BTC -> ô "Kỳ Team Building" ở thanh bên để chuyển qua lại.')
    return 0


def create_departments(db: Session) -> dict[str, Department]:
    result = {}
    for order, (code, name) in enumerate(DEPARTMENTS):
        department = Department(code=code, name=name, display_order=order)
        db.add(department)
        result[code] = department
    db.flush()
    return result


def create_work_locations(db: Session) -> dict[str, WorkLocation]:
    rows = [
        WorkLocation(code="HN", name="Hà Nội", city="Hà Nội", airport_code="HAN", display_order=1),
        WorkLocation(
            code="HCM", name="TP. Hồ Chí Minh", city="TP.HCM", airport_code="SGN", display_order=2
        ),
    ]
    db.add_all(rows)
    db.flush()
    return {row.code: row for row in rows}


def create_shifts(db: Session, event: Event) -> dict[str, Shift]:
    rows = [
        Shift(
            event_id=event.id,
            code="CA1",
            name="Ca 1 – bay sáng",
            description="Khởi hành buổi sáng, tập trung tại điểm đón từ 4h30.",
            earliest_departure="06:00",
            display_order=1,
        ),
        Shift(
            event_id=event.id,
            code="CA2",
            name="Ca 2 – bay sau giờ giao dịch",
            description="Dành cho bộ phận phải trực đến hết giờ giao dịch, bay sau 17h00.",
            earliest_departure="19:00",
            display_order=2,
        ),
    ]
    db.add_all(rows)
    db.flush()
    return {row.code: row for row in rows}


def create_trip_legs(db: Session, event: Event) -> dict[str, TripLeg]:
    rows = [
        TripLeg(
            event_id=event.id,
            code=code,
            name=name,
            direction=direction,
            is_airport_linked=linked,
            display_order=order,
            leg_date="2026-10-15" if direction == FlightDirection.OUTBOUND else "2026-10-17",
        )
        for code, name, direction, linked, order in TRIP_LEGS
    ]
    db.add_all(rows)
    db.flush()
    return {row.code: row for row in rows}


def create_pickup_points(
    db: Session, event: Event, legs: dict[str, TripLeg], locations: dict[str, WorkLocation]
) -> dict[str, PickupPoint]:
    definitions = [
        ("HN-KEANGNAM", "Toà nhà Keangnam", "Phạm Hùng, Nam Từ Liêm, Hà Nội", "HN"),
        ("HN-HOANKIEM", "Trụ sở Hoàn Kiếm", "Lý Thường Kiệt, Hoàn Kiếm, Hà Nội", "HN"),
        ("HCM-BITEXCO", "Toà nhà Bitexco", "Hải Triều, Quận 1, TP.HCM", "HCM"),
    ]
    result = {}
    for order, (key, name, address, location_code) in enumerate(definitions):
        point = PickupPoint(
            event_id=event.id,
            trip_leg_id=legs["CITY_TO_AIRPORT"].id,
            work_location_id=locations[location_code].id,
            name=name,
            address=address,
            display_order=order,
        )
        db.add(point)
        result[key] = point
    db.flush()
    return result


def create_teams(db: Session, departments: dict[str, Department]) -> list[Team]:
    teams = []
    for code, name, department_code, _size, _location, color in TEAMS:
        team = Team(
            code=code, name=name, department_id=departments[department_code].id, color=color
        )
        db.add(team)
        teams.append(team)
    db.flush()
    return teams


# --- Người dùng ---


def vietnamese_name(gender: str) -> str:
    middle = rng.choice(DEM_NAM if gender == Gender.MALE else DEM_NU)
    given = rng.choice(TEN_NAM if gender == Gender.MALE else TEN_NU)
    return f"{rng.choice(HO)} {middle} {given}"


def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt, giữ lại chữ ASCII.

    Dùng chuẩn hoá Unicode NFD rồi loại ký tự dấu, thay vì liệt kê tay từng chữ
    (cách đó bỏ sót là sinh ra email chứa dấu, không gửi được mail).
    """
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return without_marks.replace("đ", "d").replace("Đ", "D")


def unique_email(full_name: str, index: int) -> str:
    parts = strip_accents(full_name).lower().split()
    return f"{parts[-1]}{parts[0][0]}{index:03d}@company.vn"


def create_users(
    db: Session,
    teams: list[Team],
    departments: dict[str, Department],
    locations: dict[str, WorkLocation],
) -> list[User]:
    password_hash = hash_password(DEMO_PASSWORD)
    users: list[User] = []
    counter = 1

    for team, (_code, _name, department_code, size, location_code, _color) in zip(
        teams, TEAMS, strict=True
    ):
        for position in range(size):
            gender = rng.choice([Gender.MALE, Gender.FEMALE])
            full_name = vietnamese_name(gender)
            # Người đầu mỗi team làm Team Leader.
            is_leader = position == 0
            # 10% thiếu CCCD để demo cảnh báo không xuất được vé.
            has_id_card = rng.random() > 0.10

            user = User(
                employee_code=f"NV{counter:04d}",
                email=unique_email(full_name, counter),
                password_hash=password_hash,
                full_name=full_name,
                role=UserRole.TEAM_LEADER if is_leader else UserRole.EMPLOYEE,
                gender=gender,
                phone=f"09{rng.randint(10_000_000, 99_999_999)}",
                date_of_birth=f"{rng.randint(1985, 2002)}-{rng.randint(1, 12):02d}-"
                f"{rng.randint(1, 28):02d}",
                address=f"{rng.randint(1, 200)} {rng.choice(['Nguyễn Trãi', 'Lê Lợi', 'Trần Hưng Đạo', 'Nguyễn Huệ'])}, "
                f"{'Hà Nội' if location_code == 'HN' else 'TP.HCM'}",
                team_id=team.id,
                department_id=departments[department_code].id,
                work_location_id=locations[location_code].id,
                job_title="Trưởng nhóm" if is_leader else "Chuyên viên",
                id_card_number=f"0{rng.randint(10, 99)}{rng.randint(100_000_000, 999_999_999)}"
                if has_id_card
                else None,
                id_card_type="cccd" if has_id_card else None,
                shirt_size=rng.choice(SHIRT_SIZES),
                dietary_restriction=rng.choice(DIETARY),
                emergency_contact_name=vietnamese_name(rng.choice([Gender.MALE, Gender.FEMALE])),
                emergency_contact_phone=f"09{rng.randint(10_000_000, 99_999_999)}",
            )
            db.add(user)
            users.append(user)
            counter += 1

        db.flush()
        team.leader_user_id = users[-size].id

    db.flush()
    return users


def create_admins(
    db: Session, departments: dict[str, Department], locations: dict[str, WorkLocation]
) -> None:
    db.add_all(
        [
            User(
                employee_code="BTC001",
                email="btc@company.vn",
                password_hash=hash_password(ADMIN_PASSWORD),
                full_name="Ban Tổ Chức",
                role=UserRole.ADMIN,
                phone="0900000001",
                department_id=departments["HT"].id,
                work_location_id=locations["HN"].id,
                job_title="Trưởng ban tổ chức",
            ),
            User(
                employee_code="BTC000",
                email="superadmin@company.vn",
                password_hash=hash_password(ADMIN_PASSWORD),
                full_name="Quản trị hệ thống",
                role=UserRole.SUPER_ADMIN,
                phone="0900000000",
                department_id=departments["CN"].id,
                work_location_id=locations["HN"].id,
                job_title="Quản trị hệ thống",
            ),
        ]
    )
    db.flush()


# --- Chuyến bay, xe, phòng ---


def create_flights(db: Session, event: Event, shifts: dict[str, Shift]) -> list[Flight]:
    """4 chuyến: 2 chiều đi, 2 chiều về.

    Tổng ghế dùng được chiều đi = 108, trong khi ~102 người tham gia.
    Chỉ dư 6 ghế nên demo thấy rõ chuyến gần đầy và việc tách team.
    """
    # Giờ viết theo giờ Việt Nam cho dễ đối chiếu lịch trình; `vn_time` đổi sang UTC để lưu.
    definitions = [
        ("VN1234", "Vietnam Airlines", FlightDirection.OUTBOUND, "CA1", "HAN", "PQC",
         vn_time("2026-10-15", "06:30"), vn_time("2026-10-15", "08:40"), 60, 2),
        ("VN1250", "Vietnam Airlines", FlightDirection.OUTBOUND, "CA2", "HAN", "PQC",
         vn_time("2026-10-15", "19:15"), vn_time("2026-10-15", "21:25"), 52, 2),
        ("VN1235", "Vietnam Airlines", FlightDirection.RETURN, "CA1", "PQC", "HAN",
         vn_time("2026-10-17", "15:00"), vn_time("2026-10-17", "17:10"), 60, 2),
        ("VN1251", "Vietnam Airlines", FlightDirection.RETURN, "CA2", "PQC", "HAN",
         vn_time("2026-10-17", "19:30"), vn_time("2026-10-17", "21:40"), 52, 2),
    ]
    flights = []
    for (code, airline, direction, shift_code, departure, arrival,
         departure_time, arrival_time, capacity, reserved) in definitions:
        flight = Flight(
            event_id=event.id,
            flight_code=code,
            airline=airline,
            direction=direction,
            shift_id=shifts[shift_code].id,
            departure_airport=departure,
            arrival_airport=arrival,
            departure_time=departure_time,
            arrival_time=arrival_time,
            capacity=capacity,
            reserved_slots=reserved,
        )
        db.add(flight)
        flights.append(flight)
    db.flush()
    return flights


def create_buses(
    db: Session,
    event: Event,
    legs: dict[str, TripLeg],
    pickups: dict[str, PickupPoint],
    flights: list[Flight],
    users: list[User],
) -> None:
    """10 xe trải trên 4 chặng, gán sẵn trưởng xe."""
    outbound_ca1, outbound_ca2, return_ca1, return_ca2 = flights
    leaders = [user for user in users if user.role == UserRole.TEAM_LEADER]

    definitions = [
        # (chặng, mã xe, sức chứa, điểm đón, giờ tập trung, giờ chạy, chuyến bay liên quan)
        ("CITY_TO_AIRPORT", "XE-01", 45, "HN-KEANGNAM", "04:30", "04:45", outbound_ca1),
        ("CITY_TO_AIRPORT", "XE-02", 45, "HN-HOANKIEM", "04:30", "04:45", outbound_ca1),
        ("CITY_TO_AIRPORT", "XE-03", 45, "HN-KEANGNAM", "17:15", "17:30", outbound_ca2),
        ("CITY_TO_AIRPORT", "XE-04", 29, "HCM-BITEXCO", "04:00", "04:15", outbound_ca1),
        ("AIRPORT_TO_HOTEL", "XE-05", 45, None, "08:50", "09:10", outbound_ca1),
        ("AIRPORT_TO_HOTEL", "XE-06", 45, None, "21:35", "21:55", outbound_ca2),
        ("HOTEL_TO_AIRPORT", "XE-07", 45, None, "12:30", "12:45", return_ca1),
        ("HOTEL_TO_AIRPORT", "XE-08", 45, None, "16:45", "17:00", return_ca2),
        ("AIRPORT_TO_CITY", "XE-09", 45, None, "17:20", "17:40", return_ca1),
        ("AIRPORT_TO_CITY", "XE-10", 45, None, "21:50", "22:10", return_ca2),
    ]

    for index, (leg_code, bus_code, capacity, pickup_key, gather, depart, flight) in enumerate(
        definitions
    ):
        leg = legs[leg_code]
        leader = leaders[index % len(leaders)]
        db.add(
            Bus(
                event_id=event.id,
                trip_leg_id=leg.id,
                bus_code=bus_code,
                plate_number=f"29B-{rng.randint(100, 999)}.{rng.randint(10, 99)}",
                capacity=capacity,
                pickup_point_id=pickups[pickup_key].id if pickup_key else None,
                dropoff_point="Sân bay Nội Bài" if leg_code == "CITY_TO_AIRPORT" else None,
                gather_time=vn_time(leg.leg_date, gather),
                departure_time=vn_time(leg.leg_date, depart),
                leader_user_id=leader.id,
                leader_name=leader.full_name,
                leader_phone=leader.phone,
                driver_name=vietnamese_name(Gender.MALE),
                driver_phone=f"09{rng.randint(10_000_000, 99_999_999)}",
                linked_flight_id=flight.id,
            )
        )
    db.flush()


def create_hotel_and_rooms(db: Session, event: Event) -> None:
    hotel = Hotel(
        event_id=event.id,
        name="Sunset Beach Resort Phú Quốc",
        address="Đường Trần Hưng Đạo, Dương Đông, Phú Quốc",
        phone="0297 3999 888",
        # Lưu UTC: nhận phòng 14:00, trả phòng 12:00 giờ Việt Nam (+7).
        check_in_at="2026-10-15T07:00:00+00:00",
        check_out_at="2026-10-17T05:00:00+00:00",
        map_url="https://maps.google.com/?q=Sunset+Beach+Resort+Phu+Quoc",
    )
    db.add(hotel)
    db.flush()

    rooms = []
    for floor in range(8, 13):
        for number in range(1, 11):
            index = (floor - 8) * 10 + number
            rooms.append(
                Room(
                    hotel_id=hotel.id,
                    room_number=f"{floor}{number:02d}",
                    room_type="triple" if index % 5 == 0 else "twin",
                    capacity=3 if index % 5 == 0 else 2,
                    floor=str(floor),
                    gender_policy=RoomGenderPolicy.MALE
                    if index % 2
                    else RoomGenderPolicy.FEMALE,
                )
            )
    db.add_all(rooms)
    db.flush()


def create_gala(db: Session, event: Event) -> None:
    """12 bàn × 10 ghế = 120 chỗ, đủ cho toàn bộ CBNV tham gia."""
    layout = GalaLayout(
        event_id=event.id,
        name="Gala Dinner – Đêm hội Phú Quốc",
        venue="Sảnh Pearl, Sunset Beach Resort",
        starts_at=vn_time("2026-10-16", "18:30"),
        stage_position="top",
        grid_width=12,
        grid_height=8,
    )
    db.add(layout)
    db.flush()

    for index in range(12):
        table = GalaTable(
            layout_id=layout.id,
            table_code=f"B{index + 1:02d}",
            table_name=f"Bàn {index + 1}",
            seat_count=10,
            pos_x=(index % 4) * 3 + 1,
            pos_y=(index // 4) * 2 + 1,
            is_vip=index == 0,
        )
        db.add(table)
        db.flush()
        db.add_all(
            [GalaSeat(table_id=table.id, seat_number=seat) for seat in range(1, 11)]
        )
    db.flush()


def create_itinerary(db: Session, event: Event) -> None:
    schedule = [
        ("2026-10-15", "04:30", "05:00", "Tập trung tại điểm đón", "Theo xe đã phân công", "CA1"),
        ("2026-10-15", "06:30", "08:40", "Chuyến bay HAN – PQC", "Sân bay Nội Bài", "CA1"),
        ("2026-10-15", "09:30", "11:00", "Nhận phòng khách sạn", "Sunset Beach Resort", "CA1"),
        ("2026-10-15", "12:00", "13:30", "Ăn trưa", "Nhà hàng Ocean", "all"),
        ("2026-10-15", "15:00", "17:30", "Team Building bãi biển", "Bãi Trường", "all"),
        ("2026-10-15", "17:15", "17:30", "Tập trung tại điểm đón", "Theo xe đã phân công", "CA2"),
        ("2026-10-15", "19:00", "21:00", "Tiệc chào mừng", "Nhà hàng Ocean", "all"),
        ("2026-10-15", "19:15", "21:25", "Chuyến bay HAN – PQC", "Sân bay Nội Bài", "CA2"),
        ("2026-10-15", "22:00", "22:30", "Nhận phòng khách sạn", "Sunset Beach Resort", "CA2"),
        ("2026-10-15", "22:30", "23:30", "Tiệc chào mừng (ca 2)", "Nhà hàng Ocean", "CA2"),
        ("2026-10-16", "07:00", "08:30", "Ăn sáng", "Nhà hàng Ocean", "all"),
        ("2026-10-16", "09:00", "11:30", "Trò chơi vận động theo Team", "Sân trung tâm", "all"),
        ("2026-10-16", "14:00", "17:00", "Tự do / Tour Hòn Thơm", "Cáp treo Hòn Thơm", "all"),
        ("2026-10-16", "18:30", "22:00", "Gala Dinner & Vinh danh", "Sảnh Pearl", "all"),
        ("2026-10-17", "07:00", "08:30", "Ăn sáng và trả phòng", "Sunset Beach Resort", "all"),
        ("2026-10-17", "12:30", "13:00", "Tập trung ra sân bay", "Sảnh khách sạn", "CA1"),
        ("2026-10-17", "15:00", "17:10", "Chuyến bay PQC – HAN", "Sân bay Phú Quốc", "CA1"),
        ("2026-10-17", "16:45", "17:00", "Tập trung ra sân bay", "Sảnh khách sạn", "CA2"),
        ("2026-10-17", "19:30", "21:40", "Chuyến bay PQC – HAN", "Sân bay Phú Quốc", "CA2"),
    ]
    db.add_all(
        [
            ItineraryItem(
                event_id=event.id,
                day_date=day,
                start_time=start,
                end_time=end,
                title=title,
                location=location,
                audience=audience,
                display_order=order,
            )
            for order, (day, start, end, title, location, audience) in enumerate(schedule)
        ]
    )
    db.flush()


def create_content(db: Session, event: Event) -> None:
    """Quy định, FAQ, hướng dẫn — đây cũng là nguồn cho vector store của chatbot."""
    db.add_all(
        [
            PolicyDocument(
                event_id=event.id,
                doc_type=PolicyDocType.TERMS,
                title="Quy định chương trình Team Building 2026",
                content=TERMS_MARKDOWN,
                version="v1",
                updated_at=utcnow_iso(),
            ),
            PolicyDocument(
                event_id=event.id,
                doc_type=PolicyDocType.FAQ,
                title="Câu hỏi thường gặp",
                content=FAQ_MARKDOWN,
                version="v1",
                updated_at=utcnow_iso(),
            ),
            PolicyDocument(
                event_id=event.id,
                doc_type=PolicyDocType.GUIDE,
                title="Hướng dẫn sử dụng hệ thống",
                content=GUIDE_MARKDOWN,
                version="v1",
                updated_at=utcnow_iso(),
            ),
        ]
    )
    db.add_all(
        [
            Announcement(
                event_id=event.id,
                title="Mở đăng ký Team Building 2026",
                content="Hệ thống đã mở đăng ký. Hạn chót **17h00 ngày 25/09/2026**. "
                "Vui lòng cập nhật đầy đủ số CCCD và ngày sinh để BTC xuất vé máy bay.",
                severity=AnnouncementSeverity.INFO,
                published_at=utcnow_iso(),
                created_at=utcnow_iso(),
            ),
            Announcement(
                event_id=event.id,
                title="Lưu ý về đăng ký ca bay",
                content="Ca 1/Ca 2 là **nguyện vọng**. BTC sẽ phân bổ theo số slot thực tế "
                "và ưu tiên giữ các thành viên cùng Team đi chung chuyến.",
                severity=AnnouncementSeverity.WARNING,
                published_at=utcnow_iso(),
                created_at=utcnow_iso(),
            ),
        ]
    )
    db.flush()


# --- Đăng ký ---


def create_registrations(
    db: Session,
    event: Event,
    users: list[User],
    shifts: dict[str, Shift],
    legs: dict[str, TripLeg],
    pickups: dict[str, PickupPoint],
    *,
    registration_rate: float = 1.0,
) -> list[Registration]:
    """~85% CBNV tham gia. Nguyện vọng dồn về Ca 2 nhiều hơn số ghế Ca 2.

    `registration_rate < 1`: một phần CBNV chưa gửi đăng ký — để demo CBNV tự đăng ký và BTC gửi
    email nhắc. Chỉ bốc thêm số ngẫu nhiên khi dùng tỉ lệ này, nên seed mặc định vẫn ra y như cũ.
    """
    pickup_by_location = {
        "HN": [pickups["HN-KEANGNAM"], pickups["HN-HOANKIEM"]],
        "HCM": [pickups["HCM-BITEXCO"]],
    }
    registrations = []

    for user, (_c, _n, _d, _s, location_code, _col) in _users_with_location(users):
        if registration_rate < 1 and rng.random() >= registration_rate:
            continue  # chưa gửi đăng ký
        participating = rng.random() < 0.85
        # 62% muốn Ca 2 trong khi Ca 2 chỉ có 50 ghế dùng được -> chắc chắn có người lệch ca.
        shift = shifts["CA2"] if rng.random() < 0.62 else shifts["CA1"]

        registration = Registration(
            event_id=event.id,
            user_id=user.id,
            is_participating=participating,
            not_participating_reason=None if participating else "Bận việc gia đình",
            shift_id=shift.id if participating else None,
            departure_location_id=user.work_location_id,
            wish_note=rng.choice(WISH_NOTES) if participating and rng.random() < 0.3 else None,
            status=RegistrationStatus.SUBMITTED,
            submitted_at=utcnow_iso(),
        )
        db.add(registration)
        db.flush()
        registrations.append(registration)

        if not participating:
            continue

        db.add(
            Consent(
                user_id=user.id,
                event_id=event.id,
                terms_version=event.terms_version,
                agreed_at=utcnow_iso(),
                ip_address="10.0.0.1",
            )
        )
        pickup = rng.choice(pickup_by_location[location_code])
        for leg in legs.values():
            needs_bus = rng.random() < 0.8
            db.add(
                RegistrationBusNeed(
                    registration_id=registration.id,
                    trip_leg_id=leg.id,
                    needs_bus=needs_bus,
                    pickup_point_id=pickup.id
                    if needs_bus and leg.code == "CITY_TO_AIRPORT"
                    else None,
                )
            )
    db.flush()
    return registrations


def _users_with_location(users: list[User]):
    """Ghép mỗi user với dòng cấu hình team của họ để biết địa điểm làm việc."""
    pairs = []
    index = 0
    for team_config in TEAMS:
        size = team_config[3]
        for user in users[index : index + size]:
            pairs.append((user, team_config))
        index += size
    return pairs


# --- Báo cáo ---


def print_summary(
    db: Session,
    teams: list[Team],
    users: list[User],
    registrations: list[Registration],
    flights: list[Flight],
) -> None:
    participating = [r for r in registrations if r.is_participating]
    missing_id = [u for u in users if not u.id_card_number]
    outbound_capacity = sum(
        f.capacity - f.reserved_slots for f in flights if f.direction == FlightDirection.OUTBOUND
    )

    shift_counts: dict[int | None, int] = {}
    for registration in participating:
        shift_counts[registration.shift_id] = shift_counts.get(registration.shift_id, 0) + 1

    print()
    print("=" * 62)
    print("  ĐÃ NẠP DỮ LIỆU MẪU – Team Building 2026 (Phú Quốc)")
    print("=" * 62)
    print(f"  CBNV                 {len(users)} người / {len(teams)} team")
    print(f"  Đăng ký tham gia     {len(participating)} / {len(registrations)}")
    print(f"  Ghế chiều đi         {outbound_capacity} (dư {outbound_capacity - len(participating)})")
    print(f"  Nguyện vọng theo ca  {dict(sorted(shift_counts.items(), key=lambda x: x[0] or 0))}")
    print(f"  Thiếu CCCD           {len(missing_id)} người → cảnh báo không xuất được vé")
    print()
    print("  TÀI KHOẢN ĐĂNG NHẬP")
    print(f"    superadmin@company.vn   {ADMIN_PASSWORD}   (super_admin)")
    print(f"    btc@company.vn          {ADMIN_PASSWORD}   (admin – BTC)")
    for team in teams[:3]:
        leader = db.get(User, team.leader_user_id)
        print(f"    {leader.email:<24}{DEMO_PASSWORD}   (team_leader – {team.name})")
    print(f"    {users[1].email:<24}{DEMO_PASSWORD}   (employee)")
    print()
    print("  Toàn bộ CBNV dùng chung mật khẩu: " + DEMO_PASSWORD)
    print("=" * 62)


# --- Nội dung văn bản ---

TERMS_MARKDOWN = """## Quy định chương trình Team Building 2026

### 1. Đối tượng
Toàn thể CBNV đang làm việc chính thức tại công ty.

### 2. Đăng ký
- Hạn đăng ký: **17h00 ngày 25/09/2026**.
- CBNV phải cung cấp đầy đủ **họ tên, số CCCD, ngày sinh** trùng khớp giấy tờ tuỳ thân
  để BTC xuất vé máy bay. Sai lệch thông tin dẫn đến không lên được máy bay,
  CBNV tự chịu trách nhiệm.
- Ca 1 / Ca 2 là **nguyện vọng**, không phải cam kết. BTC phân bổ theo số slot thực tế.

### 3. Huỷ đăng ký và phí phạt
- Huỷ **trước 17h00 ngày 25/09/2026**: không mất phí.
- Huỷ **sau thời hạn trên**: CBNV chịu chi phí vé máy bay và phòng đã đặt,
  trừ trường hợp bất khả kháng có xác nhận của quản lý trực tiếp.
- Đăng ký nhưng không tham gia mà không báo: chịu toàn bộ chi phí.

### 4. Trong chương trình
- Tuân thủ lịch trình và hướng dẫn của Trưởng xe, Trưởng đoàn.
- Có mặt tại điểm tập trung **trước giờ khởi hành 15 phút**. Xe không chờ quá giờ.
- Không tự ý tách đoàn khi chưa báo BTC.

### 5. Liên hệ
Mọi thắc mắc gửi về Ban Tổ Chức: btc@company.vn
"""

FAQ_MARKDOWN = """## Câu hỏi thường gặp

**Tôi đăng ký Ca 2 thì có chắc chắn được bay Ca 2 không?**
Không chắc chắn. Ca 1/Ca 2 là nguyện vọng. Hệ thống ưu tiên giữ các thành viên cùng Team
đi chung một chuyến, sau đó mới tới nguyện vọng ca cá nhân. BTC sẽ thông báo kết quả
phân bổ chính thức trước ngày đi.

**Tôi có thể đổi chuyến bay sau khi BTC công bố không?**
Chỉ khi có lý do chính đáng. Gửi yêu cầu về btc@company.vn, BTC xem xét theo số slot còn lại.

**Tôi không đăng ký xe thì tự đi được không?**
Được. Bạn tự di chuyển tới sân bay và có mặt trước giờ bay theo quy định của hãng.

**Tôi bị dị ứng thức ăn thì khai ở đâu?**
Trong hồ sơ cá nhân, mục "Ghi chú ăn uống". BTC sẽ chuyển cho nhà hàng.

**Huỷ đăng ký có mất tiền không?**
Huỷ trước 17h00 ngày 25/09/2026 không mất phí. Sau thời hạn đó, CBNV chịu chi phí
vé máy bay và phòng khách sạn đã đặt.

**Tôi muốn ở chung phòng với đồng nghiệp cụ thể thì làm sao?**
Ghi nguyện vọng vào ô "Mong muốn/đề xuất" khi đăng ký. BTC cố gắng đáp ứng nhưng
ưu tiên trước là cùng giới tính và cùng Team.

**Ai là người chọn chỗ ngồi Gala Dinner cho Team tôi?**
Trưởng nhóm (Team Leader). Hệ thống bốc thăm ngẫu nhiên thứ tự các Team,
tới lượt thì Trưởng nhóm vào chọn bàn cho cả Team.
"""

GUIDE_MARKDOWN = """## Hướng dẫn sử dụng hệ thống

### Đăng nhập
Dùng email công ty và mật khẩu BTC cấp. Lần đầu đăng nhập, hệ thống yêu cầu đổi mật khẩu.

### Đăng ký tham gia
Vào mục **Đăng ký Team Building**, làm theo 5 bước: xác nhận thông tin cá nhân →
chọn tham gia hay không → chọn ca → đăng ký nhu cầu xe từng chặng → đọc quy định và gửi.
Sau khi gửi, bạn nhận email xác nhận.

### Sửa đăng ký
Vào lại mục Đăng ký, bấm **Chỉnh sửa**. Chỉ sửa được trước khi BTC đóng đăng ký.

### Xem hành trình
Mục **Hành trình của tôi** hiển thị chuyến bay đi/về, xe từng chặng kèm giờ tập trung và
số điện thoại Trưởng xe, số phòng khách sạn, bàn ghế Gala Dinner và lịch trình.
Thông tin chỉ hiện sau khi BTC công bố.

### Cập nhật hồ sơ
Mục **Hồ sơ cá nhân**: đổi ảnh đại diện, số điện thoại, địa chỉ, size áo, ghi chú ăn uống,
liên hệ khẩn cấp và số CCCD. Số CCCD và ngày sinh là bắt buộc để BTC xuất vé.

### Hỏi trợ lý ảo
Bấm nút chat góc phải dưới màn hình để hỏi về lịch trình, quy định hoặc hành trình của bạn.
"""

WISH_NOTES = [
    "Mong có nhiều hoạt động ngoài trời",
    "Đề xuất thêm thời gian tự do khám phá đảo",
    "Muốn được ngồi chung xe với team",
    "Mong BTC bố trí phòng gần thang máy",
    "Đề xuất tổ chức thêm hoạt động thể thao buổi sáng",
    "Mong có thực đơn chay cho người ăn kiêng",
]


if __name__ == "__main__":
    raise SystemExit(main())
