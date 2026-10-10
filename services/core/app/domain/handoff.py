from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Emergency, Reservation, Room, Ambulance, Handoff # type: ignore
from sqlalchemy import update, select, text

async def record_patient_received(
    db: AsyncSession, emergency_id: UUID, hospital_id: UUID, receiving_staff_ids: list[UUID] | None, actor_id: UUID
) -> None:
    """Sets offloaded_at, reservation->consumed, room->occupied, ambulance->cleaning."""
    em = await db.get(Emergency, emergency_id)
    if not em: return
    em.status = "handed_over"
    
    # reservation->consumed
    stmt = update(Reservation).where(
        Reservation.emergency_id == emergency_id, 
        Reservation.status == 'confirmed',
        Reservation.hospital_id == hospital_id
    ).values(status='consumed').returning(Reservation.room_id)
    res = await db.execute(stmt)
    room_id = res.scalar_one_or_none()
    
    if room_id:
        await db.execute(update(Room).where(Room.id == room_id).values(status='occupied'))
        
    # handoff->completed, ambulance->cleaning
    handoff = (await db.execute(select(Handoff).where(Handoff.emergency_id == emergency_id))).scalar_one_or_none()
    if handoff:
        handoff.status = 'COMPLETED'
        if handoff.ambulance_id:
            await db.execute(update(Ambulance).where(Ambulance.id == handoff.ambulance_id).values(status='cleaning'))
        
    await db.flush()

async def ambulance_arrived_hospital(session: AsyncSession, *, emergency_id: UUID | str) -> None:
    await session.execute(
        text(
            "INSERT INTO handoffs (emergency_id, hospital_id, room_id, arrived_at) "
            "SELECT id, hospital_id, NULL, now() FROM emergencies WHERE id = :id "
            "ON CONFLICT (emergency_id) DO UPDATE SET arrived_at = now()"
        ),
        {"id": str(emergency_id)},
    )
