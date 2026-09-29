from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import HospitalResource # type: ignore

class VersionConflict(Exception):
    pass

async def get_resources(db: AsyncSession, hospital_id: UUID) -> list[HospitalResource]:
    result = await db.execute(select(HospitalResource).where(HospitalResource.hospital_id == hospital_id))
    return list(result.scalars().all())

async def decrement_resource(db: AsyncSession, hospital_id: UUID, resource_type: str, quantity: int) -> bool:
    stmt = (
        update(HospitalResource)
        .where(
            HospitalResource.hospital_id == hospital_id,
            HospitalResource.resource_type == resource_type,
            HospitalResource.available >= quantity
        )
        .values(available=HospitalResource.available - quantity)
    )
    result = await db.execute(stmt)
    return result.rowcount > 0

async def increment_resource(db: AsyncSession, hospital_id: UUID, resource_type: str, quantity: int) -> None:
    stmt = (
        update(HospitalResource)
        .where(
            HospitalResource.hospital_id == hospital_id,
            HospitalResource.resource_type == resource_type
        )
        .values(available=HospitalResource.available + quantity)
    )
    await db.execute(stmt)

async def patch_resource(db: AsyncSession, resource_id: UUID, available: int, total: int | None, version: int) -> HospitalResource:
    values = {"available": available, "version": version + 1}
    if total is not None:
        values["total"] = total
        
    stmt = (
        update(HospitalResource)
        .where(HospitalResource.id == resource_id, HospitalResource.version == version)
        .values(**values)
        .returning(HospitalResource)
    )
    result = await db.execute(stmt)
    patched = result.scalar_one_or_none()
    if not patched:
        raise VersionConflict("Resource version mismatch")
    return patched
