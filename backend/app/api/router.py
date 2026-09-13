"""Gom toàn bộ router của API v1.

Thêm module mới ở đây, không include trực tiếp trong main.py.
"""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    bus_assignments,
    buses,
    emails,
    events,
    flight_assignments,
    flights,
    health,
    hotels,
    journey,
    master_data,
    registrations,
    room_assignments,
    rooms,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(events.router)
api_router.include_router(master_data.router)
api_router.include_router(registrations.router)
api_router.include_router(flights.router)
api_router.include_router(flight_assignments.router)
api_router.include_router(buses.router)
api_router.include_router(bus_assignments.router)
api_router.include_router(hotels.router)
api_router.include_router(rooms.router)
api_router.include_router(room_assignments.router)
api_router.include_router(journey.router)
api_router.include_router(emails.router)
api_router.include_router(admin.router)

# Các router sẽ thêm ở những bước sau:
# api_router.include_router(gala.router, prefix="/gala", tags=["gala"])
# api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
