"""A's file (work-distribution.md §2.2). Candidate query for dispatch rounds
(technical.md §11.1): available, KYC-verified, within radius, correct type,
recent heartbeat, not already offered for this emergency."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

HEARTBEAT_FRESH_SEC = 30


async def find_candidates(
    session: AsyncSession, *, lat: float, lng: float, radius_km: float,
    required_type: str, exclude_ambulance_ids: list[str], limit: int = 50,
) -> list[dict]:
    type_filter = "AND type = 'ALS'" if required_type == "ALS" else ""  # ALS required -> ALS only; BLS-preferred allows either
    row_sql = text(
        f"""
        SELECT id, registration_no, type,
               ST_Y(current_location::geometry) AS lat, ST_X(current_location::geometry) AS lng,
               ST_Distance(current_location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS distance_m
        FROM ambulances
        WHERE status = 'available' AND kyc_verified = true
          AND ST_DWithin(current_location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_m)
          {type_filter}
          AND last_heartbeat_at > now() - make_interval(secs => :fresh_sec)
          AND NOT (id = ANY(CAST(:exclude_ids AS uuid[])))
        ORDER BY distance_m
        LIMIT :limit
        """
    )
    rows = (await session.execute(row_sql, {
        "lat": lat, "lng": lng, "radius_m": radius_km * 1000,
        "fresh_sec": HEARTBEAT_FRESH_SEC, "exclude_ids": exclude_ambulance_ids or [],
        "limit": limit,
    })).mappings().all()
    return [dict(r) for r in rows]


async def get_ambulance(session: AsyncSession, ambulance_id: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, status, type, version, active_emergency_id FROM ambulances WHERE id = :id"),
        {"id": ambulance_id},
    )).mappings().first()
    return dict(row) if row else None
