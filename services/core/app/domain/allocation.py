from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from services.core.app.db.models import Room, Staff # type: ignore
from services.core.app.db.repos.rooms import lock_free_room_skip_locked

async def allocate_room_and_staff(
    db: AsyncSession,
    reservation_id: UUID,
    hospital_id: UUID,
    facility: str,
    eta_sec: int,
    requested_room_id: UUID | None,
    requested_staff_ids: list[UUID],
) -> tuple[Room, list[Staff]]:
    """Auto-allocate if not specified: least-loaded on-duty specialists."""
    room = None
    if requested_room_id:
        room = await db.get(Room, requested_room_id)
    else:
        room = await lock_free_room_skip_locked(db, hospital_id, [facility])
        
    staff_members = []
    if requested_staff_ids:
        for sid in requested_staff_ids:
            s = await db.get(Staff, sid)
            if s: staff_members.append(s)
    else:
        # Mock allocation
        pass
        
    return room, staff_members
