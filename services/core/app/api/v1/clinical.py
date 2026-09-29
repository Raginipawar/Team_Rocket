from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...security.deps import require_role
from ...db.engine import get_db
from ...domain.clinical import (
    confirm_triage, 
    trigger_critical_deterioration, 
    get_family_override_options, 
    execute_family_override, 
    record_refused_transport
)

router = APIRouter(prefix="/emergencies", tags=["clinical"])

class TriageConfirmRequest(BaseModel):
    acuity: str
    facility: str
    patient_count: int
    version: int

class FamilyOverrideRequest(BaseModel):
    hospital_id: UUID
    consent: bool

class RefusedTransportRequest(BaseModel):
    note: Optional[str] = None

@router.post("/{id}/triage-confirm")
async def triage_confirm_endpoint(
    id: UUID,
    payload: TriageConfirmRequest,
    user = Depends(require_role('paramedic')),
    db: AsyncSession = Depends(get_db)
):
    try:
        res = await confirm_triage(
            db, 
            emergency_id=id, 
            acuity=payload.acuity, 
            facility=payload.facility, 
            patient_count=payload.patient_count,
            version=payload.version,
            actor_id=user.id
        )
        return {"status": "confirmed", "triage": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": "BAD_REQUEST", "message": str(e)}})
    except Exception as e:
        raise HTTPException(status_code=409, detail={"error": {"code": "CONFLICT", "message": str(e)}})

@router.post("/{id}/critical")
async def critical_deterioration_endpoint(
    id: UUID,
    user = Depends(require_role('paramedic')),
    db: AsyncSession = Depends(get_db)
):
    await trigger_critical_deterioration(db, emergency_id=id, actor_id=user.id)
    return {"status": "triggered"}

@router.get("/{id}/family-override/options")
async def family_override_options_endpoint(
    id: UUID,
    user = Depends(require_role('paramedic')),
    db: AsyncSession = Depends(get_db)
):
    options = await get_family_override_options(db, emergency_id=id)
    return {"data": options}

@router.post("/{id}/family-override")
async def family_override_endpoint(
    id: UUID,
    payload: FamilyOverrideRequest,
    user = Depends(require_role('paramedic')),
    db: AsyncSession = Depends(get_db)
):
    if not payload.consent:
        raise HTTPException(status_code=400, detail={"error": {"code": "CONSENT_REQUIRED", "message": "Consent is required for family override"}})
    
    await execute_family_override(
        db, 
        emergency_id=id, 
        hospital_id=payload.hospital_id, 
        actor_id=user.id
    )
    return {"status": "overridden"}

@router.post("/{id}/refused-transport")
async def refused_transport_endpoint(
    id: UUID,
    payload: RefusedTransportRequest,
    user = Depends(require_role('paramedic')),
    db: AsyncSession = Depends(get_db)
):
    await record_refused_transport(db, emergency_id=id, note=payload.note, actor_id=user.id)
    return {"status": "recorded"}
