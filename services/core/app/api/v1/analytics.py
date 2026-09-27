"""A's file (work-distribution.md §2.2). technical.md §11.16: hospital-scoped
+ system-wide analytics. Hospital staff see only their own hospital_id
(enforced by require_hospital_scope); developer/ops role sees everything."""

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.db.session import get_session
from app.security.deps import CurrentUser, require_role

router = APIRouter()


@router.get("/hospital/{hospital_id}/analytics")
async def hospital_analytics(hospital_id: str, user: CurrentUser = Depends(require_role("hospital_staff", "developer"))) -> dict:
    if user.role == "hospital_staff" and user.hospital_id != hospital_id:
        from fastapi import HTTPException
        raise HTTPException(403, "not scoped to this hospital")

    async with get_session() as session:
        response_times = (await session.execute(
            text("SELECT * FROM mv_response_times WHERE hospital_id = :h"), {"h": hospital_id},
        )).mappings().first()
        offload = (await session.execute(
            text("SELECT * FROM mv_offload_delay WHERE hospital_id = :h"), {"h": hospital_id},
        )).mappings().first()
        outcomes = (await session.execute(
            text("SELECT * FROM v_hospital_request_outcomes WHERE hospital_id = :h"), {"h": hospital_id},
        )).mappings().all()
        rejection_rate = (await session.execute(
            text("SELECT * FROM v_hospital_rejection_rate_24h WHERE hospital_id = :h"), {"h": hospital_id},
        )).mappings().first()
        stale = (await session.execute(
            text("SELECT * FROM v_stale_data_frequency WHERE hospital_id = :h"), {"h": hospital_id},
        )).mappings().first()

    return {
        "response_times": dict(response_times) if response_times else None,
        "offload_delay": dict(offload) if offload else None,
        "request_outcomes": [dict(r) for r in outcomes],
        "rejection_rate_24h": dict(rejection_rate) if rejection_rate else None,
        "stale_data": dict(stale) if stale else None,
    }


@router.get("/ops/analytics")
async def system_analytics(user: CurrentUser = Depends(require_role("developer"))) -> dict:
    async with get_session() as session:
        response_times = (await session.execute(text("SELECT * FROM mv_response_times"))).mappings().all()
        triage_confusion = (await session.execute(text("SELECT * FROM v_triage_confusion_matrix"))).mappings().all()
        triage_recall = (await session.execute(text("SELECT * FROM v_triage_critical_recall"))).mappings().first()
        escalations = (await session.execute(text("SELECT * FROM v_escalation_stats"))).mappings().all()
        demand = (await session.execute(text("SELECT * FROM v_demand_actual_vs_forecast LIMIT 200"))).mappings().all()
        mci = (await session.execute(text("SELECT * FROM v_mci_events ORDER BY created_at DESC LIMIT 50"))).mappings().all()
        prank_dup = (await session.execute(text("SELECT * FROM v_prank_duplicate_counts"))).mappings().first()

    return {
        "response_times_by_hospital": [dict(r) for r in response_times],
        "triage_confusion_matrix": [dict(r) for r in triage_confusion],
        "triage_critical_recall": dict(triage_recall) if triage_recall else None,
        "escalations": [dict(r) for r in escalations],
        "demand_actual_vs_forecast": [dict(r) for r in demand],
        "mci_events": [dict(r) for r in mci],
        "prank_duplicate_counts": dict(prank_dup) if prank_dup else None,
    }


@router.post("/ops/analytics/refresh")
async def refresh_materialized_views(user: CurrentUser = Depends(require_role("developer"))) -> dict:
    """Stand-in for the real 'refresh each minute' job (technical.md §11.16) --
    B's job scheduler doesn't exist yet, so this is a manual trigger until it
    does. Concurrent refresh needs a unique index, which both MVs have."""
    async with get_session() as session:
        await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_response_times"))
        await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_offload_delay"))
        await session.commit()
    return {"refreshed": ["mv_response_times", "mv_offload_delay"]}
