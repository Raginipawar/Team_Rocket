from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Emergency, Reservation, Room, Ambulance # type: ignore
from sqlalchemy import update

async def record_patient_received(
    db: AsyncSession, emergency_id: UUID, receiving_staff_ids: list[UUID]
) -> None:
    """Sets offloaded_at, reservation->consumed, room->occupied, ambulance->cleaning."""
    em = await db.get(Emergency, emergency_id)
    if not em: return
    em.status = "handed_over"
    
    # reservation->consumed
    stmt = update(Reservation).where(Reservation.emergency_id == emergency_id, Reservation.status == 'confirmed').values(status='consumed').returning(Reservation.room_id)
    res = await db.execute(stmt)
    room_id = res.scalar_one_or_none()
    
    if room_id:
        await db.execute(update(Room).where(Room.id == room_id).values(status='occupied'))
        
    # ambulance->cleaning
    if em.ambulance_id:
        await db.execute(update(Ambulance).where(Ambulance.id == em.ambulance_id).values(status='cleaning'))
        
    await db.flush()
