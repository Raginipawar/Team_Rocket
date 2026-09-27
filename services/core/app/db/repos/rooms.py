from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
from services.core.app.db.models import Room # type: ignore

class RoomReserved(Exception):
    pass

class VersionConflict(Exception):
    pass

async def get_room(db: AsyncSession, room_id: UUID) -> Room:
    result = await db.execute(select(Room).where(Room.id == room_id))
    return result.scalar_one_or_none()

async def list_rooms(db: AsyncSession, hospital_id: UUID) -> list[Room]:
    result = await db.execute(select(Room).where(Room.hospital_id == hospital_id))
    return list(result.scalars().all())

async def lock_free_room_skip_locked(db: AsyncSession, hospital_id: UUID, acceptable_types: list[str]) -> Room | None:
    stmt = (
        select(Room)
        .where(Room.hospital_id == hospital_id, Room.type.in_(acceptable_types), Room.status == 'free')
        .order_by(Room.priority_order)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def update_room_status(db: AsyncSession, room_id: UUID, status: str, reservation_id: UUID | None, version: int) -> Room:
    stmt = (
        update(Room)
        .where(Room.id == room_id, Room.version == version)
        .values(status=status, reservation_id=reservation_id, version=version + 1)
        .returning(Room)
    )
    result = await db.execute(stmt)
    room = result.scalar_one_or_none()
    if not room:
        raise VersionConflict(f"Room {room_id} version mismatch or not found")
    return room

async def patch_room(db: AsyncSession, room_id: UUID, status: str, version: int, override_reason: str | None) -> Room:
    # 409 ROOM_RESERVED guard
    room = await get_room(db, room_id)
    if not room:
        raise ValueError("Room not found")
    if room.status == 'reserved' and status != 'reserved':
        raise RoomReserved("Cannot patch a reserved room without releasing reservation first")
        
    stmt = (
        update(Room)
        .where(Room.id == room_id, Room.version == version)
        .values(status=status, override_reason=override_reason, version=version + 1)
        .returning(Room)
    )
    result = await db.execute(stmt)
    patched = result.scalar_one_or_none()
    if not patched:
        raise VersionConflict("Version mismatch")
    return patched
