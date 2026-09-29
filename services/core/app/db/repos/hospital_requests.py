"""Repository for hospital_requests (dispatch offers / inbound patient requests)."""
from uuid import UUID
from typing import Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.dispatch import HospitalRequest


async def list_pending_requests(db: AsyncSession, hospital_id: UUID) -> list[dict]:
    """Return all pending hospital requests for a hospital."""
    result = await db.execute(
        select(HospitalRequest).where(
            HospitalRequest.hospital_id == hospital_id,
            HospitalRequest.status == "pending",
        ).order_by(HospitalRequest.created_at.asc())
    )
    rows = result.scalars().all()
    return [_to_dict(r) for r in rows]


async def list_all_requests(
    db: AsyncSession,
    hospital_id: UUID,
    status: Optional[str] = None,
) -> list[dict]:
    """Return hospital requests filtered by optional status."""
    q = select(HospitalRequest).where(HospitalRequest.hospital_id == hospital_id)
    if status:
        q = q.where(HospitalRequest.status == status)
    q = q.order_by(HospitalRequest.created_at.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [_to_dict(r) for r in rows]


async def get_hospital_request(db: AsyncSession, request_id: UUID) -> Optional[HospitalRequest]:
    result = await db.execute(
        select(HospitalRequest).where(HospitalRequest.id == request_id)
    )
    return result.scalar_one_or_none()


def _to_dict(r: HospitalRequest) -> dict:
    return {
        "id": str(r.id),
        "emergency_id": str(r.emergency_id),
        "hospital_id": str(r.hospital_id),
        "status": r.status,
        "rank": r.rank,
        "explanation": r.explanation,
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
