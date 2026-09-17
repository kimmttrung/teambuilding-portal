"""Gom toàn bộ router của API v1.

Thêm module mới ở đây, không include trực tiếp trong main.py.
"""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    announcements,
    auth,
    bus_assignments,
    buses,
    cancellations,
    emails,
    events,
    flight_assignments,
    flights,
    gala,
    health,
    hotels,
    itinerary,
    journey,
    master_data,
    people,
    policy_documents,
    registrations,
    reminders,
    room_assignments,
    rooms,
    team_leaders,
    users,
    chat
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(events.router)
api_router.include_router(master_data.router)
api_router.include_router(policy_documents.router)
api_router.include_router(people.router)
api_router.include_router(registrations.router)
api_router.include_router(cancellations.router)
api_router.include_router(team_leaders.router)
api_router.include_router(flights.router)
api_router.include_router(flight_assignments.router)
api_router.include_router(buses.router)
api_router.include_router(bus_assignments.router)
api_router.include_router(hotels.router)
api_router.include_router(rooms.router)
api_router.include_router(room_assignments.router)
api_router.include_router(itinerary.router)
api_router.include_router(journey.router)
api_router.include_router(emails.router)
api_router.include_router(admin.router)
api_router.include_router(reminders.router)
api_router.include_router(users.router)
api_router.include_router(gala.router)
api_router.include_router(chat.router)
api_router.include_router(chat.admin_router)
api_router.include_router(announcements.router)

