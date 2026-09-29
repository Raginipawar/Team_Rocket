"""Repository for Staff and StaffShift models."""
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.hospitals import Staff, StaffShift


async def get_active_staff(db: AsyncSession, hospital_id: UUID) -> list[dict]:
    """Return staff currently on an active shift at this hospital."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Staff).where(
            Staff.hospital_id == hospital_id,
            Staff.is_active == True,
        )
    )
    rows = result.scalars().all()
    return [_staff_to_dict(s) for s in rows]


async def list_staff_members(db: AsyncSession, hospital_id: UUID) -> list[dict]:
    """Return all staff for a hospital."""
    result = await db.execute(
        select(Staff).where(Staff.hospital_id == hospital_id).order_by(Staff.name)
    )
    rows = result.scalars().all()
    return [_staff_to_dict(s) for s in rows]


async def create_staff_member(
    db: AsyncSession,
    hospital_id: UUID,
    name: str,
    role: str,
) -> dict:
    """Create a new staff member (specialty = role)."""
    staff = Staff(
        hospital_id=hospital_id,
        name=name,
        specialty=role,
        is_active=True,
    )
    db.add(staff)
    await db.commit()
    await db.refresh(staff)
    return _staff_to_dict(staff)


async def get_shifts(
    db: AsyncSession,
    staff_id: UUID,
    hospital_id: UUID,
) -> list[dict]:
    """Return all shifts for a staff member, scoped to hospital."""
    # First verify staff belongs to this hospital
    staff_result = await db.execute(
        select(Staff).where(Staff.id == staff_id, Staff.hospital_id == hospital_id)
    )
    staff = staff_result.scalar_one_or_none()
    if not staff:
        return []

    result = await db.execute(
        select(StaffShift)
        .where(StaffShift.staff_id == staff_id)
        .order_by(StaffShift.start_at.desc())
    )
    rows = result.scalars().all()
    return [_shift_to_dict(s) for s in rows]


async def update_shifts(
    db: AsyncSession,
    staff_id: UUID,
    hospital_id: UUID,
    shifts: list[dict],
) -> None:
    """Replace/add shifts for a staff member."""
    # Verify ownership
    staff_result = await db.execute(
        select(Staff).where(Staff.id == staff_id, Staff.hospital_id == hospital_id)
    )
    staff = staff_result.scalar_one_or_none()
    if not staff:
        return

    for shift_data in shifts:
        shift = StaffShift(
            staff_id=staff_id,
            start_at=shift_data.get("start_at"),
            end_at=shift_data.get("end_at"),
            role_override=shift_data.get("role_override"),
        )
        db.add(shift)
    await db.commit()


def _staff_to_dict(s: Staff) -> dict:
    return {
        "id": str(s.id),
        "hospital_id": str(s.hospital_id),
        "name": s.name,
        "specialty": s.specialty,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _shift_to_dict(s: StaffShift) -> dict:
    return {
        "id": str(s.id),
        "staff_id": str(s.staff_id),
        "start_at": s.start_at.isoformat() if s.start_at else None,
        "end_at": s.end_at.isoformat() if s.end_at else None,
    }
