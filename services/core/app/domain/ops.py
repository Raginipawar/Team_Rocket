"""Ops domain logic — ops dashboard, escalation management, manual overrides, sim control."""
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.db.models.emergencies import Emergency
from app.db.models.ambulances import Ambulance
from app.db.models.hospitals import Hospital
from app.db.models.control import Escalation, OneTimeToken, AuditLog
from app.db.repos.escalations import (
    get_escalation,
    claim_escalation as repo_claim_escalation,
    resolve_escalation as repo_resolve_escalation,
    list_open_escalations,
)
from app.db.repos.analytics import get_ops_analytics as repo_get_ops_analytics


async def create_ops_session(db: AsyncSession, token: str) -> dict:
    """Exchange a one-time token for an ops session."""
    result = await db.execute(
        select(OneTimeToken).where(OneTimeToken.token == token, OneTimeToken.used == False)
    )
    ott = result.scalar_one_or_none()
    if not ott:
        raise ValueError("Invalid or expired token")
    ott.used = True
    await db.commit()
    return {
        "cookie": f"ott:{token}",
        "user": {"id": str(ott.user_id), "role": "ops"},
    }


async def get_overview(db: AsyncSession) -> dict:
    """Return live overview: emergencies, ambulances, hospitals, open escalations."""
    emergencies = (await db.execute(
        select(Emergency).where(Emergency.status.not_in(["handed_off", "cancelled", "closed"]))
    )).scalars().all()

    ambulances = (await db.execute(
        select(Ambulance).where(Ambulance.status != "offline")
    )).scalars().all()

    hospitals = (await db.execute(select(Hospital))).scalars().all()

    escalations = await list_open_escalations(db)

    return {
        "live_emergencies": [{"id": str(e.id), "status": e.status} for e in emergencies],
        "ambulances": [{"id": str(a.id), "status": a.status} for a in ambulances],
        "hospitals": [{"id": str(h.id), "name": h.name} for h in hospitals],
        "open_escalations": [{"id": str(e.id), "type": e.escalation_type} for e in escalations],
    }


async def get_escalation_details(db: AsyncSession, escalation_id: UUID) -> Optional[dict]:
    """Return full escalation details."""
    esc = await get_escalation(db, escalation_id)
    if not esc:
        return None
    return {
        "id": str(esc.id),
        "type": esc.escalation_type,
        "status": esc.status,
        "context": esc.context,
        "options": esc.options,
        "claimed_by": str(esc.claimed_by) if esc.claimed_by else None,
        "created_at": esc.created_at.isoformat() if esc.created_at else None,
    }


async def claim_escalation(db: AsyncSession, escalation_id: UUID, ops_user_id: UUID) -> None:
    """Claim an escalation (CAS)."""
    await repo_claim_escalation(db, escalation_id, ops_user_id)


async def resolve_escalation(
    db: AsyncSession,
    escalation_id: UUID,
    option_id: UUID,
    ops_user_id: UUID,
) -> None:
    """Resolve an escalation with chosen option (only claimer can resolve)."""
    esc = await get_escalation(db, escalation_id)
    if not esc:
        raise ValueError("Escalation not found")
    if esc.claimed_by != ops_user_id:
        raise ValueError("Only the claimer can resolve this escalation")
    await repo_resolve_escalation(db, escalation_id, str(option_id), claimer_id=ops_user_id)


async def manual_override(
    db: AsyncSession,
    emergency_id: UUID,
    hospital_id: UUID,
    reason: str,
    actor_id: UUID,
) -> None:
    """Manually assign emergency to a hospital (ops override)."""
    em = await db.get(Emergency, emergency_id)
    if not em:
        raise ValueError("Emergency not found")
    em.status = "hospital_selecting"
    # Trigger selection to the specific hospital
    from app.domain.audit import write as audit_write
    await audit_write(db, "emergency", emergency_id, actor_id, "manual_override", {
        "hospital_id": str(hospital_id),
        "reason": reason,
    })
    await db.commit()


async def get_ops_analytics(db: AsyncSession, from_date: str, to_date: str) -> dict:
    """System-wide analytics."""
    return await repo_get_ops_analytics(db, from_date, to_date)


async def get_ops_audit(db: AsyncSession, entity_id: UUID) -> list[dict]:
    """Return audit log entries for an entity."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.record_id == entity_id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "table_name": r.table_name,
            "action": r.action,
            "actor_id": str(r.actor_id) if r.actor_id else None,
            "changes": r.changes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def list_scenarios(db: AsyncSession) -> list[str]:
    """List available simulation scenario names."""
    from pathlib import Path
    scenarios_dir = Path("/app/app/sim/scenarios")
    if not scenarios_dir.exists():
        return []
    return [f.stem for f in scenarios_dir.glob("*.yaml")]


async def run_scenario(db: AsyncSession, scenario_name: str) -> None:
    """Run a named simulation scenario."""
    # Stub — full implementation in sim/runner.py
    pass


async def sim_reset(db: AsyncSession) -> None:
    """Reset all simulated data to initial state."""
    await db.execute(text("UPDATE emergencies SET status='cancelled' WHERE is_simulated=true AND status NOT IN ('handed_off','cancelled','closed')"))
    await db.execute(text("UPDATE ambulances SET status='available' WHERE is_simulated=true"))
    await db.commit()


async def sim_speed(db: AsyncSession, multiplier: int) -> None:
    """Update simulation speed multiplier (no-op stub)."""
    # Speed multiplier is stored in memory in the sim world
    pass
