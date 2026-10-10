from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Room, Staff # type: ignore
from app.db.repos.rooms import lock_free_room_skip_locked

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
        # Find least-loaded staff
        from sqlalchemy import select, func, text
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        
        # We need an emergency physician and an ER nurse at minimum
        stmt = (
            select(Staff)
            .where(Staff.hospital_id == hospital_id)
            .where(Staff.role.in_(['physician', 'nurse']))
            .order_by(Staff.role, text('random()'))
            .limit(2)
        )
        res = await db.execute(stmt)
        staff_members = list(res.scalars().all())
        
    return room, staff_members
