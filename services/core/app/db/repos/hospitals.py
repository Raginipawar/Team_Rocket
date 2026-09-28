from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, text
from app.db.models.hospitals import Hospital, HospitalResource

async def get_hospital(db: AsyncSession, hospital_id: UUID) -> Hospital:
    result = await db.execute(select(Hospital).where(Hospital.id == hospital_id))
    return result.scalar_one_or_none()

async def list_hospitals_within_km(db: AsyncSession, lat: float, lng: float, radius_km: float) -> list[Hospital]:
    stmt = text("""
        SELECT id FROM hospitals 
        WHERE ST_DWithin(location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_m)
    """)
    result = await db.execute(stmt, {"lat": lat, "lng": lng, "radius_m": radius_km * 1000})
    hospital_ids = [row[0] for row in result.fetchall()]
    if not hospital_ids:
        return []
    res = await db.execute(select(Hospital).where(Hospital.id.in_(hospital_ids)))
    return res.scalars().all()

async def update_last_confirmed(db: AsyncSession, hospital_id: UUID) -> None:
    now = func.now()
    await db.execute(
        update(Hospital)
        .where(Hospital.id == hospital_id)
        .values(last_confirmed_at=now)
    )
    await db.execute(
        update(HospitalResource)
        .where(HospitalResource.hospital_id == hospital_id)
        .values(reported_at=now)
    )
