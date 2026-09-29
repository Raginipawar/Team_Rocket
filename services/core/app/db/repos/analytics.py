"""Repository for analytics queries (hospital + ops dashboards)."""
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_hospital_analytics(
    db: AsyncSession,
    hospital_id: UUID,
    from_date: str,
    to_date: str,
) -> dict:
    """Return aggregated analytics for a hospital in a date range."""
    result = await db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'handed_off') AS total_handoffs,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS total_cancellations,
                AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) FILTER (WHERE status = 'handed_off') AS avg_turnaround_sec
            FROM hospital_requests
            WHERE hospital_id = :hospital_id
              AND created_at BETWEEN :from_date AND :to_date
        """),
        {"hospital_id": str(hospital_id), "from_date": from_date, "to_date": to_date},
    )
    row = result.mappings().one_or_none()
    if not row:
        return {"total_handoffs": 0, "total_cancellations": 0, "avg_turnaround_sec": None}
    return dict(row)


async def get_ops_analytics(
    db: AsyncSession,
    from_date: str,
    to_date: str,
) -> dict:
    """Return system-wide analytics for the ops dashboard."""
    result = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total_emergencies,
                COUNT(*) FILTER (WHERE status = 'handed_off') AS completed,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
                AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) FILTER (WHERE status = 'handed_off') AS avg_resolution_sec
            FROM emergencies
            WHERE created_at BETWEEN :from_date AND :to_date
        """),
        {"from_date": from_date, "to_date": to_date},
    )
    row = result.mappings().one_or_none()
    if not row:
        return {}
    return dict(row)
