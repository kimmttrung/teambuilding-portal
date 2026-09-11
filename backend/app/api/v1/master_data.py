"""Endpoint master data: nguồn cho mọi dropdown trong hệ thống.

CBNV đọc được (để hiện form đăng ký), chỉ BTC sửa được.
Xoá một mục đang được tham chiếu sẽ bị chặn — xoá team còn người là dữ liệu mồ côi.
"""

from fastapi import APIRouter, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import AdminUser, CurrentUser, DbSession, get_client_ip
from app.core.exceptions import ConflictError, NotFoundError
from app.models.event import Event
from app.models.flight import Flight, Shift
from app.models.org import Department, Team, WorkLocation
from app.models.registration import Registration, RegistrationBusNeed
from app.models.transportation import Bus, PickupPoint, TripLeg
from app.models.user import User
from app.schemas.master_data import (
    DepartmentIn,
    DepartmentOut,
    DepartmentUpdate,
    PickupPointIn,
    PickupPointOut,
    PickupPointUpdate,
    RegistrationFormOptions,
    ShiftIn,
    ShiftOut,
    ShiftUpdate,
    TeamIn,
    TeamOut,
    TeamUpdate,
    TripLegIn,
    TripLegOut,
    TripLegUpdate,
    WorkLocationIn,
    WorkLocationOut,
    WorkLocationUpdate,
)
from app.services import audit_service, event_service

router = APIRouter(prefix="/master-data", tags=["master-data"])


# --- Tiện ích dùng chung ---


def _get_or_404(db: Session, model, item_id: int, label: str):
    instance = db.get(model, item_id)
    if instance is None:
        raise NotFoundError(f"Không tìm thấy {label} #{item_id}.")
    return instance


def _ensure_unique_code(db: Session, model, code: str, label: str, event_id: int | None = None):
    query = select(model).where(model.code == code)
    if event_id is not None:
        query = query.where(model.event_id == event_id)
    if db.scalar(query):
        raise ConflictError(f"Mã {label} '{code}' đã tồn tại.", code="CODE_DUPLICATED")


def _count(db: Session, model, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def _block_delete_if_used(usages: dict[str, int], label: str) -> None:
    """Chặn xoá khi còn dữ liệu tham chiếu, và nói rõ vướng ở đâu."""
    blocking = {name: count for name, count in usages.items() if count}
    if blocking:
        detail = ", ".join(f"{count} {name}" for name, count in blocking.items())
        raise ConflictError(
            f"Không xoá được {label} vì đang được dùng: {detail}. "
            "Hãy chuyển dữ liệu sang mục khác trước, hoặc đặt is_active = false để ẩn đi.",
            code="ENTITY_IN_USE",
            details=blocking,
        )


def _active_event(db: Session) -> Event:
    event = event_service.get_active_event(db)
    if event is None:
        raise NotFoundError("Chưa có kỳ Team Building nào đang mở.", code="NO_ACTIVE_EVENT")
    return event


def _audit(db, request, actor, action, entity_type, entity_id, before=None, after=None) -> None:
    audit_service.log(
        db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor.id,
        before=before,
        after=after,
        ip_address=get_client_ip(request),
    )
    db.commit()


# --- Gói cho form đăng ký ---


@router.get(
    "/registration-form",
    response_model=RegistrationFormOptions,
    summary="Toàn bộ lựa chọn cho form đăng ký (1 request)",
)
def get_registration_form_options(db: DbSession, _: CurrentUser) -> RegistrationFormOptions:
    event = _active_event(db)
    return RegistrationFormOptions(
        teams=_list_teams(db),
        departments=[
            DepartmentOut.model_validate(row)
            for row in db.scalars(
                select(Department)
                .where(Department.is_active.is_(True))
                .order_by(Department.display_order, Department.name)
            )
        ],
        work_locations=[
            WorkLocationOut.model_validate(row)
            for row in db.scalars(
                select(WorkLocation)
                .where(WorkLocation.is_active.is_(True))
                .order_by(WorkLocation.display_order)
            )
        ],
        shifts=[
            ShiftOut.model_validate(row)
            for row in db.scalars(
                select(Shift).where(Shift.event_id == event.id).order_by(Shift.display_order)
            )
        ],
        trip_legs=[
            TripLegOut.model_validate(row)
            for row in db.scalars(
                select(TripLeg)
                .where(TripLeg.event_id == event.id)
                .order_by(TripLeg.display_order)
            )
        ],
        pickup_points=[
            PickupPointOut.model_validate(row)
            for row in db.scalars(
                select(PickupPoint)
                .where(PickupPoint.event_id == event.id)
                .order_by(PickupPoint.display_order)
            )
        ],
    )


# --- Phòng ban ---


@router.get("/departments", response_model=list[DepartmentOut], summary="Danh sách phòng ban")
def list_departments(db: DbSession, _: CurrentUser) -> list[DepartmentOut]:
    rows = db.scalars(select(Department).order_by(Department.display_order, Department.name))
    return [DepartmentOut.model_validate(row) for row in rows]


@router.post(
    "/departments",
    response_model=DepartmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm phòng ban",
)
def create_department(
    payload: DepartmentIn, actor: AdminUser, db: DbSession, request: Request
) -> DepartmentOut:
    _ensure_unique_code(db, Department, payload.code, "phòng ban")
    department = Department(**payload.model_dump())
    db.add(department)
    db.flush()
    _audit(db, request, actor, "department.created", "department", department.id,
           after=payload.model_dump())
    return DepartmentOut.model_validate(department)


@router.patch("/departments/{item_id}", response_model=DepartmentOut, summary="Sửa phòng ban")
def update_department(
    item_id: int, payload: DepartmentUpdate, actor: AdminUser, db: DbSession, request: Request
) -> DepartmentOut:
    department = _get_or_404(db, Department, item_id, "phòng ban")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(department, field, value)
    db.flush()
    _audit(db, request, actor, "department.updated", "department", item_id, after=changes)
    return DepartmentOut.model_validate(department)


@router.delete(
    "/departments/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá phòng ban"
)
def delete_department(item_id: int, actor: AdminUser, db: DbSession, request: Request) -> None:
    department = _get_or_404(db, Department, item_id, "phòng ban")
    _block_delete_if_used(
        {
            "team": _count(db, Team, Team.department_id == item_id),
            "CBNV": _count(db, User, User.department_id == item_id),
        },
        "phòng ban",
    )
    db.delete(department)
    _audit(db, request, actor, "department.deleted", "department", item_id,
           before={"code": department.code, "name": department.name})


# --- Địa điểm làm việc ---


@router.get("/work-locations", response_model=list[WorkLocationOut], summary="Địa điểm làm việc")
def list_work_locations(db: DbSession, _: CurrentUser) -> list[WorkLocationOut]:
    rows = db.scalars(select(WorkLocation).order_by(WorkLocation.display_order))
    return [WorkLocationOut.model_validate(row) for row in rows]


@router.post(
    "/work-locations",
    response_model=WorkLocationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm địa điểm làm việc",
)
def create_work_location(
    payload: WorkLocationIn, actor: AdminUser, db: DbSession, request: Request
) -> WorkLocationOut:
    _ensure_unique_code(db, WorkLocation, payload.code, "địa điểm")
    location = WorkLocation(**payload.model_dump())
    db.add(location)
    db.flush()
    _audit(db, request, actor, "work_location.created", "work_location", location.id,
           after=payload.model_dump())
    return WorkLocationOut.model_validate(location)


@router.patch(
    "/work-locations/{item_id}", response_model=WorkLocationOut, summary="Sửa địa điểm làm việc"
)
def update_work_location(
    item_id: int, payload: WorkLocationUpdate, actor: AdminUser, db: DbSession, request: Request
) -> WorkLocationOut:
    location = _get_or_404(db, WorkLocation, item_id, "địa điểm")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(location, field, value)
    db.flush()
    _audit(db, request, actor, "work_location.updated", "work_location", item_id, after=changes)
    return WorkLocationOut.model_validate(location)


@router.delete(
    "/work-locations/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xoá địa điểm làm việc",
)
def delete_work_location(item_id: int, actor: AdminUser, db: DbSession, request: Request) -> None:
    location = _get_or_404(db, WorkLocation, item_id, "địa điểm")
    _block_delete_if_used(
        {
            "CBNV": _count(db, User, User.work_location_id == item_id),
            "đăng ký": _count(db, Registration, Registration.departure_location_id == item_id),
        },
        "địa điểm làm việc",
    )
    db.delete(location)
    _audit(db, request, actor, "work_location.deleted", "work_location", item_id,
           before={"code": location.code})


# --- Team ---


def _list_teams(db: Session) -> list[TeamOut]:
    """Kèm số thành viên — BTC cần con số này để ước lượng slot và quota ghế Gala."""
    counts = dict(
        db.execute(
            select(User.team_id, func.count(User.id))
            .where(User.is_active.is_(True))
            .group_by(User.team_id)
        ).all()
    )
    rows = db.scalars(select(Team).order_by(Team.name))
    return [
        TeamOut.model_validate(row).model_copy(update={"member_count": counts.get(row.id, 0)})
        for row in rows
    ]


@router.get("/teams", response_model=list[TeamOut], summary="Danh sách team")
def list_teams(db: DbSession, _: CurrentUser) -> list[TeamOut]:
    return _list_teams(db)


@router.post(
    "/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED, summary="Thêm team"
)
def create_team(
    payload: TeamIn, actor: AdminUser, db: DbSession, request: Request
) -> TeamOut:
    _ensure_unique_code(db, Team, payload.code, "team")
    _validate_team_refs(db, payload.department_id, payload.leader_user_id)
    team = Team(**payload.model_dump())
    db.add(team)
    db.flush()
    _audit(db, request, actor, "team.created", "team", team.id, after=payload.model_dump())
    return TeamOut.model_validate(team)


@router.patch("/teams/{item_id}", response_model=TeamOut, summary="Sửa team")
def update_team(
    item_id: int, payload: TeamUpdate, actor: AdminUser, db: DbSession, request: Request
) -> TeamOut:
    team = _get_or_404(db, Team, item_id, "team")
    changes = payload.model_dump(exclude_unset=True)
    _validate_team_refs(db, changes.get("department_id"), changes.get("leader_user_id"))
    for field, value in changes.items():
        setattr(team, field, value)
    db.flush()
    _audit(db, request, actor, "team.updated", "team", item_id, after=changes)
    member_count = _count(db, User, User.team_id == item_id, User.is_active.is_(True))
    return TeamOut.model_validate(team).model_copy(update={"member_count": member_count})


@router.delete("/teams/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá team")
def delete_team(item_id: int, actor: AdminUser, db: DbSession, request: Request) -> None:
    team = _get_or_404(db, Team, item_id, "team")
    _block_delete_if_used(
        {"CBNV": _count(db, User, User.team_id == item_id)}, f"team '{team.name}'"
    )
    db.delete(team)
    _audit(db, request, actor, "team.deleted", "team", item_id, before={"code": team.code})


def _validate_team_refs(db: Session, department_id: int | None, leader_user_id: int | None) -> None:
    """teams.leader_user_id không có FOREIGN KEY (vòng lặp với users) nên phải tự kiểm."""
    if department_id is not None and db.get(Department, department_id) is None:
        raise NotFoundError(f"Không tìm thấy phòng ban #{department_id}.")
    if leader_user_id is not None and db.get(User, leader_user_id) is None:
        raise NotFoundError(f"Không tìm thấy CBNV #{leader_user_id} để làm trưởng nhóm.")


# --- Ca bay (theo kỳ) ---


@router.get("/shifts", response_model=list[ShiftOut], summary="Danh sách ca bay của kỳ hiện tại")
def list_shifts(db: DbSession, _: CurrentUser) -> list[ShiftOut]:
    event = _active_event(db)
    rows = db.scalars(
        select(Shift).where(Shift.event_id == event.id).order_by(Shift.display_order)
    )
    return [ShiftOut.model_validate(row) for row in rows]


@router.post(
    "/shifts", response_model=ShiftOut, status_code=status.HTTP_201_CREATED, summary="Thêm ca bay"
)
def create_shift(
    payload: ShiftIn, actor: AdminUser, db: DbSession, request: Request
) -> ShiftOut:
    event = _active_event(db)
    _ensure_unique_code(db, Shift, payload.code, "ca bay", event_id=event.id)
    shift = Shift(event_id=event.id, **payload.model_dump())
    db.add(shift)
    db.flush()
    _audit(db, request, actor, "shift.created", "shift", shift.id, after=payload.model_dump())
    return ShiftOut.model_validate(shift)


@router.patch("/shifts/{item_id}", response_model=ShiftOut, summary="Sửa ca bay")
def update_shift(
    item_id: int, payload: ShiftUpdate, actor: AdminUser, db: DbSession, request: Request
) -> ShiftOut:
    shift = _get_or_404(db, Shift, item_id, "ca bay")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(shift, field, value)
    db.flush()
    _audit(db, request, actor, "shift.updated", "shift", item_id, after=changes)
    return ShiftOut.model_validate(shift)


@router.delete("/shifts/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá ca bay")
def delete_shift(item_id: int, actor: AdminUser, db: DbSession, request: Request) -> None:
    shift = _get_or_404(db, Shift, item_id, "ca bay")
    _block_delete_if_used(
        {
            "đăng ký": _count(db, Registration, Registration.shift_id == item_id),
            "chuyến bay": _count(db, Flight, Flight.shift_id == item_id),
        },
        f"ca '{shift.name}'",
    )
    db.delete(shift)
    _audit(db, request, actor, "shift.deleted", "shift", item_id, before={"code": shift.code})


# --- Chặng xe (theo kỳ) ---


@router.get("/trip-legs", response_model=list[TripLegOut], summary="Các chặng di chuyển")
def list_trip_legs(db: DbSession, _: CurrentUser) -> list[TripLegOut]:
    event = _active_event(db)
    rows = db.scalars(
        select(TripLeg).where(TripLeg.event_id == event.id).order_by(TripLeg.display_order)
    )
    return [TripLegOut.model_validate(row) for row in rows]


@router.post(
    "/trip-legs",
    response_model=TripLegOut,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm chặng",
)
def create_trip_leg(
    payload: TripLegIn, actor: AdminUser, db: DbSession, request: Request
) -> TripLegOut:
    event = _active_event(db)
    _ensure_unique_code(db, TripLeg, payload.code, "chặng", event_id=event.id)
    leg = TripLeg(event_id=event.id, **payload.model_dump())
    db.add(leg)
    db.flush()
    _audit(db, request, actor, "trip_leg.created", "trip_leg", leg.id, after=payload.model_dump())
    return TripLegOut.model_validate(leg)


@router.patch("/trip-legs/{item_id}", response_model=TripLegOut, summary="Sửa chặng")
def update_trip_leg(
    item_id: int, payload: TripLegUpdate, actor: AdminUser, db: DbSession, request: Request
) -> TripLegOut:
    leg = _get_or_404(db, TripLeg, item_id, "chặng")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(leg, field, value)
    db.flush()
    _audit(db, request, actor, "trip_leg.updated", "trip_leg", item_id, after=changes)
    return TripLegOut.model_validate(leg)


@router.delete("/trip-legs/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá chặng")
def delete_trip_leg(item_id: int, actor: AdminUser, db: DbSession, request: Request) -> None:
    leg = _get_or_404(db, TripLeg, item_id, "chặng")
    _block_delete_if_used(
        {
            "xe": _count(db, Bus, Bus.trip_leg_id == item_id),
            "nhu cầu xe đã đăng ký": _count(
                db, RegistrationBusNeed, RegistrationBusNeed.trip_leg_id == item_id
            ),
        },
        f"chặng '{leg.name}'",
    )
    db.delete(leg)
    _audit(db, request, actor, "trip_leg.deleted", "trip_leg", item_id, before={"code": leg.code})


# --- Điểm đón (theo kỳ) ---


@router.get("/pickup-points", response_model=list[PickupPointOut], summary="Điểm đón/trả")
def list_pickup_points(db: DbSession, _: CurrentUser) -> list[PickupPointOut]:
    event = _active_event(db)
    rows = db.scalars(
        select(PickupPoint)
        .where(PickupPoint.event_id == event.id)
        .order_by(PickupPoint.display_order)
    )
    return [PickupPointOut.model_validate(row) for row in rows]


@router.post(
    "/pickup-points",
    response_model=PickupPointOut,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm điểm đón",
)
def create_pickup_point(
    payload: PickupPointIn, actor: AdminUser, db: DbSession, request: Request
) -> PickupPointOut:
    event = _active_event(db)
    point = PickupPoint(event_id=event.id, **payload.model_dump())
    db.add(point)
    db.flush()
    _audit(db, request, actor, "pickup_point.created", "pickup_point", point.id,
           after=payload.model_dump())
    return PickupPointOut.model_validate(point)


@router.patch(
    "/pickup-points/{item_id}", response_model=PickupPointOut, summary="Sửa điểm đón"
)
def update_pickup_point(
    item_id: int, payload: PickupPointUpdate, actor: AdminUser, db: DbSession, request: Request
) -> PickupPointOut:
    point = _get_or_404(db, PickupPoint, item_id, "điểm đón")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(point, field, value)
    db.flush()
    _audit(db, request, actor, "pickup_point.updated", "pickup_point", item_id, after=changes)
    return PickupPointOut.model_validate(point)


@router.delete(
    "/pickup-points/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá điểm đón"
)
def delete_pickup_point(item_id: int, actor: AdminUser, db: DbSession, request: Request) -> None:
    point = _get_or_404(db, PickupPoint, item_id, "điểm đón")
    _block_delete_if_used(
        {
            "xe": _count(db, Bus, Bus.pickup_point_id == item_id),
            "đăng ký nhu cầu xe": _count(
                db, RegistrationBusNeed, RegistrationBusNeed.pickup_point_id == item_id
            ),
        },
        f"điểm đón '{point.name}'",
    )
    db.delete(point)
    _audit(db, request, actor, "pickup_point.deleted", "pickup_point", item_id,
           before={"name": point.name})
