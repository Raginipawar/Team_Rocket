"""Ops domain logic — ops dashboard, escalation management, manual overrides, sim control."""
from uuid import UUID
from typing import Optional
from datetime import datetime
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
    """Exchange a one-time token for an ops session.

    Was querying OneTimeToken.token/.used -- neither column exists on the
    real one_time_tokens table (db/migrations/0001_init.sql: token_hash as
    the PK, used_at as a nullable timestamp, issued_to not user_id). Every
    real call would have raised UndefinedColumnError. Rewritten against the
    real schema with raw SQL, same pattern already used elsewhere in this
    router for tables with no matching ORM model."""
    from app.security.tokens import hash_token
    token_hash = hash_token(token)
    row = (await db.execute(
        text("SELECT token_hash, escalation_id, issued_to, expires_at, used_at FROM one_time_tokens "
             "WHERE token_hash = :h AND purpose = 'ops'"),
        {"h": token_hash},
    )).mappings().first()
    if not row or row["used_at"] is not None or row["expires_at"] < datetime.utcnow().replace(tzinfo=row["expires_at"].tzinfo):
        raise ValueError("Invalid or expired token")
    await db.execute(
        text("UPDATE one_time_tokens SET used_at = now() WHERE token_hash = :h"), {"h": token_hash},
    )
    await db.commit()
    return {
        "cookie": f"ott:{token}",
        "escalation_id": str(row["escalation_id"]) if row["escalation_id"] else None,
        "user": {"id": str(row["issued_to"]) if row["issued_to"] else None, "role": "ops"},
    }


async def issue_ops_token(db: AsyncSession, *, escalation_id: UUID | str | None = None,
                           emergency_id: UUID | str | None = None) -> str:
    """Generates the one-time link sent in a Telegram escalation alert.
    Returns the full URL (PUBLIC_BASE_URL + /ops/<raw token>) -- the raw
    token is handed out exactly once, only its SHA-256 hash is stored."""
    from app.config import settings
    from app.security.tokens import new_token
    from datetime import timedelta

    raw, token_hash = new_token()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OPS_LINK_TTL_MIN)
    await db.execute(
        text("INSERT INTO one_time_tokens (token_hash, purpose, escalation_id, emergency_id, expires_at) "
             "VALUES (:h, 'ops', :esc, :em, :exp)"),
        {"h": token_hash, "esc": str(escalation_id) if escalation_id else None,
         "em": str(emergency_id) if emergency_id else None, "exp": expires_at},
    )
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/ops/{raw}"


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
        "type": esc.type,
        "status": esc.status,
        "summary": esc.summary,
        "options": esc.options,
        "default_option_id": esc.default_option_id,
        "chosen_option_id": esc.chosen_option_id,
        "claimed_by": str(esc.claimed_by) if esc.claimed_by else None,
        "created_at": esc.created_at.isoformat() if esc.created_at else None,
    }


async def claim_escalation(db: AsyncSession, escalation_id: UUID, ops_user_id: UUID) -> None:
    """Claim an escalation (CAS)."""
    await repo_claim_escalation(db, escalation_id, ops_user_id)


async def resolve_escalation(
    db: AsyncSession,
    escalation_id: UUID,
    option_id: str,
    ops_user_id: UUID,
) -> None:
    """Resolve an escalation with chosen option (only claimer can resolve)."""
    esc = await get_escalation(db, escalation_id)
    if not esc:
        raise ValueError("Escalation not found")
    # esc.claimed_by is a real uuid.UUID (ORM-mapped); ops_user_id arrives as
    # a plain str (CurrentUser.id, security/deps.py) -- UUID != str is
    # ALWAYS true in Python regardless of value, so this rejected literally
    # every claimer, including the real one, every time. Confirmed by
    # actually claiming then resolving with the same real user and getting
    # FORBIDDEN anyway.
    if str(esc.claimed_by) != str(ops_user_id):
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
    before_status = em.status
    em.status = "hospital_selecting"

    from app.domain.audit import write as audit_write
    # Real signature is keyword-only (actor_type, actor_id, entity,
    # entity_id, action, before, after) -- the previous positional call
    # would have raised TypeError on the first real override, same bug
    # pattern already found and fixed in domain/clinical.py this session.
    await audit_write(
        db, actor_type="user", actor_id=str(actor_id), entity="emergencies",
        entity_id=emergency_id, action="manual_override",
        before={"status": before_status}, after={"status": "hospital_selecting", "hospital_id": str(hospital_id), "reason": reason},
    )

    from app.domain.reservations import create_hospital_request_with_hold
    acuity = em.acuity or "urgent"
    facility = em.facility or "general"
    await create_hospital_request_with_hold(
        db, emergency_id=emergency_id, hospital_id=hospital_id, rank=1, features={},
        explanation=[f"Manually overridden by ops: {reason}"], acuity=acuity, facility=facility,
    )
    await db.commit()


async def get_ops_analytics(db: AsyncSession, from_date: str, to_date: str) -> dict:
    """System-wide analytics."""
    return await repo_get_ops_analytics(db, from_date, to_date)


async def get_ops_audit(
    db: AsyncSession,
    entity_id: UUID | None = None,
    actor_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> list[dict]:
    """Return audit log entries, optionally filtered by entity/actor/time range."""
    query = select(AuditLog)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    if actor_id:
        # AuditLog.actor_id is Text (real schema), not UUID -- comparing it
        # against a UUID object instead of str is the same silently-always-
        # False bug class already found and fixed elsewhere this session
        # (domain/ops.py's old claimer check, hospital.py's _check_scope).
        query = query.where(AuditLog.actor_id == str(actor_id))
    if from_time:
        query = query.where(AuditLog.at >= from_time)
    if to_time:
        query = query.where(AuditLog.at <= to_time)
    result = await db.execute(query.order_by(AuditLog.at.desc()).limit(100))
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "entity": r.entity,
            "action": r.action,
            "actor_type": r.actor_type,
            "actor_id": r.actor_id,
            "before": r.before,
            "after": r.after,
            "at": r.at.isoformat() if r.at else None,
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
