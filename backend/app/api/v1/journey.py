"""My Journey (docs/04-api-spec.md §9).

`/journey/me` lấy người dùng từ JWT, không bao giờ từ tham số — đổi số trên URL không xem
được hành trình người khác. BTC tra cứu hộ qua `/journey/{user_id}`.

`/journey/me/pdf` (nice-to-have) chưa làm.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import ActiveEvent, CurrentUser, DbSession, require_admin
from app.schemas.journey import JourneyOut
from app.services import journey_service

router = APIRouter(prefix="/journey", tags=["journey"])


@router.get("/me", response_model=JourneyOut, summary="Toàn bộ hành trình của tôi")
def my_journey(user: CurrentUser, event: ActiveEvent, db: DbSession) -> JourneyOut:
    return JourneyOut(**journey_service.build_journey(db, event=event, user=user))


@router.get(
    "/{user_id}",
    response_model=JourneyOut,
    dependencies=[Depends(require_admin)],
    summary="BTC tra cứu hành trình của một CBNV",
)
def journey_of(user_id: int, event: ActiveEvent, db: DbSession) -> JourneyOut:
    user = journey_service.require_user(db, user_id)
    return JourneyOut(**journey_service.build_journey(db, event=event, user=user))
