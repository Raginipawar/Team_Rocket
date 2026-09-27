from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from services.core.app.domain.selection import start_selection
from services.core.app.integrations.ml.routing import get_eta, hospital_rank
from services.core.app.db.models import Emergency, Ambulance, Reservation, Patient # type: ignore
from services.core.app.db.repos.reservations import release_reservation
from sqlalchemy import update, select

DETERIORATION_DIVERT_GAIN_SEC = 300

async def handle_deterioration(db: AsyncSession, emergency_id: UUID, ml_client, redis_client) -> None:
    em = await db.get(Emergency, emergency_id)
    if not em or em.status not in ["hospital_confirmed", "transporting"]: return
    
    # Check current ETA
    # Find new candidates and check if new_ETA < current_ETA - DETERIORATION_DIVERT_GAIN_SEC
    # Divert if gain >= DETERIORATION_DIVERT_GAIN_SEC
    # Mocking implementation for ML call
    old_eta = await get_eta(ml_client, "amb_loc", "old_hosp", None)
    new_eta = await get_eta(ml_client, "amb_loc", "new_hosp", None)
    
    if old_eta["seconds"] - new_eta["seconds"] >= DETERIORATION_DIVERT_GAIN_SEC:
        await start_selection(db, redis_client, ml_client, emergency_id, trigger="deterioration")

async def handle_triage_change(db: AsyncSession, emergency_id: UUID, new_acuity: str, new_facility: str, ml_client, redis_client) -> None:
    em = await db.get(Emergency, emergency_id)
    if not em: return
    
    re_run_selection = False
    if em.acuity != new_acuity or em.facility != new_facility:
        re_run_selection = True
        
    em.acuity = new_acuity
    em.facility = new_facility
    
    if re_run_selection:
        await start_selection(db, redis_client, ml_client, emergency_id, trigger="triage_change")

async def get_family_override_options(db: AsyncSession, emergency_id: UUID) -> list[dict]:
    # Mock returning eligible hospitals with time/resource deltas
    return [
        {"hospital_id": "hosp-1", "name": "City General", "time_delta_mins": +5, "capability_gaps": [], "staleness": 1},
        {"hospital_id": "hosp-2", "name": "Mercy Care", "time_delta_mins": +12, "capability_gaps": ["ventilator"], "staleness": 3}
    ]

async def apply_family_override(db: AsyncSession, emergency_id: UUID, hospital_id: UUID) -> None:
    from services.core.app.domain.reservations import create_hospital_request_with_hold
    # Create request with is_family_choice=True
    # Assuming mocked dependencies
    await create_hospital_request_with_hold(
        db,
        emergency_id=emergency_id,
        hospital_id=hospital_id,
        rank=1,
        features={},
        explanation=["Family override requested"],
        acuity="red",
        facility="ICU",
        is_family_choice=True
    )

async def handle_refused_transport(db: AsyncSession, emergency_id: UUID, note: str) -> None:
    em = await db.get(Emergency, emergency_id)
    if not em: return
    
    em.status = "refused_transport"
    
    if em.ambulance_id:
        await db.execute(update(Ambulance).where(Ambulance.id == em.ambulance_id).values(status='idle'))
        
    stmt = select(Reservation).where(Reservation.emergency_id == emergency_id, Reservation.status.in_(['held', 'confirmed']))
    result = await db.execute(stmt)
    res = result.scalar_one_or_none()
    
    if res:
        await release_reservation(db, res.id, "released")

async def handle_unknown_patient_merge(db: AsyncSession, temp_id: str, phone: str, merged_by: UUID) -> None:
    stmt = select(Patient).where(Patient.temp_id == temp_id)
    result = await db.execute(stmt)
    temp_pat = result.scalar_one_or_none()
    
    if temp_pat:
        # Merge logic, audit
        from services.core.app.domain.audit import write as audit_write
        await audit_write(db, "patient", temp_pat.id, merged_by, "merge", {"old_id": temp_id, "new_phone": phone})
        temp_pat.phone = phone
        temp_pat.is_unknown = False
