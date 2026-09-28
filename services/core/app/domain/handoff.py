"""DRAFT stub -- real owner is Person B (work-distribution.md §2.2, §11.6
room/staff allocation on accept). A's geofence code (domain/lifecycle.py)
calls this exact signature (work-distribution.md §4.2) when an ambulance
enters the hospital geofence, but hospital selection/reservations don't
exist yet (B hasn't started), so this just writes the handoffs row's
arrived_at and leaves room/staff allocation for B's real implementation."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ambulance_arrived_hospital(session: AsyncSession, *, emergency_id: UUID | str) -> None:
    await session.execute(
        text(
            "INSERT INTO handoffs (emergency_id, hospital_id, room_id, arrived_at) "
            "SELECT id, hospital_id, NULL, now() FROM emergencies WHERE id = :id "
            "ON CONFLICT (emergency_id) DO UPDATE SET arrived_at = now()"
        ),
        {"id": str(emergency_id)},
    )
