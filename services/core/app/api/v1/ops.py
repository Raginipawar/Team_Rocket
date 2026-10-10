# Every protected endpoint below used require_role('ops') -- but the real
# users.role CHECK constraint (db/migrations/0001_init.sql) only allows
# patient/paramedic/hospital_staff/developer. There is no 'ops' role in the
# database, so no user could ever pass this check -- every one of these
# endpoints was unreachable by anyone, found by actually calling one with a
# real token and getting 403, not by reading the code. Fixed to the real
# role name (same fix already made in domain/privacy.py for the same
# ops-vs-developer mismatch). Separately, /session below establishes an
# httpOnly cookie session while every OTHER endpoint here checks the JWT
# bearer role instead of that cookie -- two different auth mechanisms for
# the same router, not unified by this fix. Flagged, not solved: unifying
# them means deciding whether ops auth is cookie-based (technical.md
# Section7.7's stated design) or JWT-based (what actually works today).
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...security.deps import require_role
from ...db.engine import get_db
from ...domain.ops import (
    create_ops_session,
    get_overview,
    get_escalation_details,
    claim_escalation,
    resolve_escalation,
    manual_override,
    get_ops_analytics,
    get_ops_audit,
    list_scenarios,
    run_scenario,
    sim_reset,
    sim_speed
)

router = APIRouter(prefix="/ops", tags=["ops"])

class ResolveEscalationRequest(BaseModel):
    # Escalation options are plain string ids (e.g. "opt1"), matching the
    # real chosen_option_id/default_option_id TEXT columns -- UUID here
    # would reject every real option id with a 422, confirmed by actually
    # calling this endpoint with a real option id and getting exactly that.
    option_id: str

class OverrideEmergencyRequest(BaseModel):
    hospital_id: UUID
    reason: str

class SpeedSimulationRequest(BaseModel):
    multiplier: int

class SessionRequest(BaseModel):
    token: str

@router.post("/session")
async def ops_session_endpoint(
    payload: SessionRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    try:
        session_data = await create_ops_session(db, token=payload.token)
        response.set_cookie(key="ops_session", value=session_data["cookie"], max_age=7200, httponly=True)
        return {"status": "ok", "user": session_data["user"]}
    except ValueError as e:
        raise HTTPException(status_code=401, detail={"error": {"code": "INVALID_TOKEN", "message": str(e)}})

@router.get("/overview")
async def ops_overview_endpoint(
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    data = await get_overview(db)
    return {"data": data}

@router.get("/escalations/{id}")
async def get_escalation_endpoint(
    id: UUID,
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    data = await get_escalation_details(db, escalation_id=id)
    if not data:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Escalation not found"}})
    return {"data": data}

@router.post("/escalations/{id}/claim")
async def claim_escalation_endpoint(
    id: UUID,
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    try:
        await claim_escalation(db, escalation_id=id, ops_user_id=user.id)
        await db.commit()
        return {"status": "claimed"}
    except ValueError as e:
        raise HTTPException(status_code=409, detail={"error": {"code": "CONFLICT", "message": str(e)}})

@router.post("/escalations/{id}/resolve")
async def resolve_escalation_endpoint(
    id: UUID,
    payload: ResolveEscalationRequest,
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    try:
        await resolve_escalation(db, escalation_id=id, option_id=payload.option_id, ops_user_id=user.id)
        await db.commit()
        return {"status": "resolved"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": str(e)}})

@router.post("/emergencies/{id}/override")
async def override_emergency_endpoint(
    id: UUID,
    payload: OverrideEmergencyRequest,
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    if not payload.reason:
        raise HTTPException(status_code=400, detail={"error": {"code": "BAD_REQUEST", "message": "Reason is mandatory"}})
    await manual_override(db, emergency_id=id, hospital_id=payload.hospital_id, reason=payload.reason, actor_id=user.id)
    return {"status": "overridden"}

@router.get("/analytics")
async def ops_analytics_endpoint(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    data = await get_ops_analytics(db, from_date=from_date, to_date=to_date)
    return {"data": data}

@router.get("/audit")
async def ops_audit_endpoint(
    entity_id: UUID,
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    data = await get_ops_audit(db, entity_id=entity_id)
    return {"data": data}

@router.get("/scenarios")
async def list_scenarios_endpoint(
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    data = await list_scenarios(db)
    return {"data": data}

@router.post("/scenarios/{name}/run")
async def run_scenario_endpoint(
    name: str,
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    await run_scenario(db, scenario_name=name)
    return {"status": "running"}

@router.post("/sim/reset")
async def sim_reset_endpoint(
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    await sim_reset(db)
    return {"status": "reset"}

@router.post("/sim/speed")
async def sim_speed_endpoint(
    payload: SpeedSimulationRequest,
    user = Depends(require_role('developer')),
    db: AsyncSession = Depends(get_db)
):
    await sim_speed(db, multiplier=payload.multiplier)
    return {"status": "updated"}
