"""BTC tra cứu "người này đang ở đâu": chuyến bay, xe từng chặng, phòng, ghế Gala.

Hai endpoint tách nhau có chủ đích: ô tìm gõ tới đâu gọi tới đó nên phải nhẹ (`/search` chỉ trả tên +
team), còn vị trí đầy đủ chỉ lấy một lần sau khi đã chọn đúng người (`/{user_id}/location`).
"""

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import ActiveEvent, DbSession, require_admin
from app.schemas.people import PersonLocation, PersonSearchItem
from app.services import people_locator_service

router = APIRouter(
    prefix="/admin/people", tags=["people"], dependencies=[Depends(require_admin)]
)


@router.get(
    "/search",
    response_model=list[PersonSearchItem],
    summary="Gợi ý người theo tên / email / mã NV",
)
def search_people(
    event: ActiveEvent,
    db: DbSession,
    q: str = Query(description="Tên, email hoặc mã nhân viên"),
    limit: int = Query(default=people_locator_service.SEARCH_LIMIT, ge=1, le=50),
) -> list[PersonSearchItem]:
    return [
        PersonSearchItem(**row)
        for row in people_locator_service.search(db, event=event, query=q, limit=limit)
    ]


@router.get(
    "/{user_id}/location",
    response_model=PersonLocation,
    summary="Vị trí chính xác của một người trong kỳ",
)
def locate_person(user_id: int, event: ActiveEvent, db: DbSession) -> PersonLocation:
    """Trả cả phần **chưa** xếp (`None`) để BTC thấy còn thiếu gì, và không chặn theo `published`
    như `/journey/{user_id}` — BTC chính là người đang xếp."""
    return PersonLocation(**people_locator_service.locate(db, event=event, user_id=user_id))
