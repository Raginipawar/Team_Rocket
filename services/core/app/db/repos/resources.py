from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HospitalResource  # type: ignore


class VersionConflict(Exception):
    pass


async def get_resources(db: AsyncSession, hospital_id: UUID) -> list[HospitalResource]:
    result = await db.execute(select(HospitalResource).where(HospitalResource.hospital_id == hospital_id))
    return list(result.scalars().all())


async def decrement_resource(db: AsyncSession, hospital_id: UUID, resource_type: str, quantity: int) -> bool:
    """technical.md §11.3 bundle step: available -= q, reserved += q,
    all-or-nothing (0 rows -> caller rolls back and tries the next hospital).
    The previous version only touched `available`, which breaks the
    available+reserved<=total invariant the schema's own CHECK constraint
    enforces -- fixed to update both."""
    stmt = (
        update(HospitalResource)
        .where(
            HospitalResource.hospital_id == hospital_id,
            HospitalResource.type == resource_type,
            HospitalResource.available >= quantity,
        )
        .values(available=HospitalResource.available - quantity, reserved=HospitalResource.reserved + quantity)
    )
    result = await db.execute(stmt)
    return result.rowcount > 0


async def increment_resource(db: AsyncSession, hospital_id: UUID, resource_type: str, quantity: int) -> None:
    """Release path: credit back available, release the matching reserved
    amount (mirrors decrement_resource -- previously only touched available).

    Unlike decrement_resource, this had no floor guard: if `reserved` was
    already lower than `quantity` (e.g. a hold that was never actually
    applied to reserved in the first place, or a resource count overwritten
    by a later sync without preserving reserved), this pushed reserved
    negative and crashed on the schema's own `reserved >= 0` CHECK -- found
    by a real reject action 500ing, not by reading the code. Releasing only
    min(quantity, reserved) can never go negative, and since it just moves
    that amount from reserved to available (sum unchanged), the schema's
    other invariant (available + reserved <= total) stays satisfied too."""
    await db.execute(text(
        "UPDATE hospital_resources SET "
        "available = available + LEAST(:qty, reserved), "
        "reserved = reserved - LEAST(:qty, reserved), "
        "updated_at = now() "
        "WHERE hospital_id = :hid AND type = :rtype"
    ), {"qty": quantity, "hid": str(hospital_id), "rtype": resource_type})


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
