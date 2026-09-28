from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import Reservation, Room # type: ignore
from .resources import increment_resource

async def create_reservation(db: AsyncSession, **kwargs) -> Reservation:
    res = Reservation(**kwargs)
    db.add(res)
    await db.flush()
    return res

async def get_active_reservation(db: AsyncSession, emergency_id: UUID) -> Reservation | None:
    stmt = select(Reservation).where(
        Reservation.emergency_id == emergency_id,
        Reservation.status.in_(['held', 'confirmed'])
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def extend_hold(db: AsyncSession, reservation_id: UUID, new_expires_at: datetime) -> None:
    await db.execute(
        update(Reservation)
        .where(Reservation.id == reservation_id, Reservation.status == 'held')
        .values(expires_at=new_expires_at)
    )

async def release_reservation(db: AsyncSession, reservation_id: UUID, status: str) -> None:
    res = await db.get(Reservation, reservation_id)
    if not res:
        return
        
    await db.execute(
        update(Reservation).where(Reservation.id == reservation_id).values(status=status)
    )
    
    if res.room_id:
        room = await db.get(Room, res.room_id)
        if room:
            await db.execute(
                update(Room).where(Room.id == res.room_id).values(status='free', reservation_id=None)
            )
            
    # Load items and increment resources
    for item in res.items:
        if item.resource_type:
            await increment_resource(db, res.hospital_id, item.resource_type, item.quantity)
