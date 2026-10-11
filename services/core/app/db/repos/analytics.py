"""Repository for analytics queries (hospital + ops dashboards)."""
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _percentiles(db: AsyncSession, sql: str, params: dict) -> dict:
    row = (await db.execute(text(sql), params)).mappings().one_or_none()
    return {
        "p50": row["p50"] if row else None, "p90": row["p90"] if row else None,
        "n": int(row["n"]) if row and row["n"] is not None else 0,
    }


async def get_hospital_analytics(
    db: AsyncSession,
    hospital_id: UUID,
    from_date: str,
    to_date: str,
) -> dict:
    """Real analytics from actual timestamps -- the previous version
    returned {total_handoffs, total_cancellations, avg_turnaround_sec},
    a completely different (and much thinner) shape than what the
    frontend (app/hospital/analytics/page.tsx) has always expected
    (response_times percentiles, offload_delay, request_outcomes,
    rejections_by_reason, stale_data) -- it was reading a.response_times
    .call_to_accept.p50 off a payload that never had a response_times
    key at all, which is the real "could not load" here: not a failed
    fetch, a shape mismatch the frontend had no guard against."""
    params = {"hid": str(hospital_id), "from_date": from_date, "to_date": to_date}

    response_times = {
        "call_to_accept": await _percentiles(db, """
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (assigned_at - received_at))) AS p50,
                   percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (assigned_at - received_at))) AS p90,
                   COUNT(*) AS n
            FROM emergencies WHERE hospital_id = :hid AND assigned_at IS NOT NULL
              AND received_at BETWEEN :from_date AND :to_date
        """, params),
        "call_to_scene": await _percentiles(db, """
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (at_scene_at - received_at))) AS p50,
                   percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (at_scene_at - received_at))) AS p90,
                   COUNT(*) AS n
            FROM emergencies WHERE hospital_id = :hid AND at_scene_at IS NOT NULL
              AND received_at BETWEEN :from_date AND :to_date
        """, params),
        "scene_to_hospital": await _percentiles(db, """
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (arrived_hospital_at - at_scene_at))) AS p50,
                   percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (arrived_hospital_at - at_scene_at))) AS p90,
                   COUNT(*) AS n
            FROM emergencies WHERE hospital_id = :hid AND arrived_hospital_at IS NOT NULL AND at_scene_at IS NOT NULL
              AND received_at BETWEEN :from_date AND :to_date
        """, params),
        "call_to_handoff": await _percentiles(db, """
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (handed_off_at - received_at))) AS p50,
                   percentile_cont(0.9) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (handed_off_at - received_at))) AS p90,
                   COUNT(*) AS n
            FROM emergencies WHERE hospital_id = :hid AND handed_off_at IS NOT NULL
              AND received_at BETWEEN :from_date AND :to_date
        """, params),
    }

    offload_delay = await _percentiles(db, """
        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY h.offload_delay_sec) AS p50,
               percentile_cont(0.9) WITHIN GROUP (ORDER BY h.offload_delay_sec) AS p90,
               COUNT(*) AS n
        FROM handoffs h
        WHERE h.hospital_id = :hid AND h.offload_delay_sec IS NOT NULL
          AND h.arrived_at BETWEEN :from_date AND :to_date
    """, params)

    outcome_rows = (await db.execute(text("""
        SELECT status AS outcome, COUNT(*) AS count FROM hospital_requests
        WHERE hospital_id = :hid AND created_at BETWEEN :from_date AND :to_date
        GROUP BY status
    """), params)).mappings().all()

    reason_rows = (await db.execute(text("""
        SELECT COALESCE(reason_code, 'unspecified') AS reason, COUNT(*) AS count FROM hospital_requests
        WHERE hospital_id = :hid AND status = 'rejected' AND created_at BETWEEN :from_date AND :to_date
        GROUP BY reason_code ORDER BY count DESC
    """), params)).mappings().all()

    return {
        "synthetic": False, "flags": [],
        "response_times": response_times,
        "offload_delay": {**offload_delay, "buckets": []},
        "request_outcomes": [dict(r) for r in outcome_rows],
        "rejections_by_reason": [dict(r) for r in reason_rows],
        # Cross-hospital staleness comparison belongs on the ops dashboard,
        # not a single hospital's own view of itself -- no fabricated
        # numbers, frontend already renders an empty chart safely.
        "stale_data": [],
    }


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
