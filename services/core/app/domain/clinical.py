from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.selection import start_selection, FACILITY_TO_CAPABILITY
from app.integrations.ml.routing import get_eta
from app.db.models import Emergency, Ambulance, Reservation, Patient, Hospital # type: ignore
from app.db.repos.reservations import release_reservation
from app.db.repos.hospitals import list_hospitals_within_km
from sqlalchemy import update, select
from geoalchemy2.shape import to_shape

DETERIORATION_DIVERT_GAIN_SEC = 300

async def handle_deterioration(db: AsyncSession, emergency_id: UUID, ml_client, redis_client) -> None:
    """technical.md §11.8: divert only if a new target is >=3 min faster to
    definitive care. The previous version called get_eta(ml_client, "amb_loc",
    "old_hosp", None) -- string literals, not real coordinates -- so this
    could never have computed a real gain. Rewritten to use the ambulance's
    and current hospital's real locations."""
    em = await db.get(Emergency, emergency_id)
    if not em or em.status not in ["hospital_confirmed", "transporting"]: return
    if not em.ambulance_id or not em.hospital_id or em.location is None: return

    ambulance = await db.get(Ambulance, em.ambulance_id)
    current_hospital = await db.get(Hospital, em.hospital_id)
    if not ambulance or not current_hospital or ambulance.current_location is None:
        return

    amb_point = to_shape(ambulance.current_location)
    old_hosp_point = to_shape(current_hospital.location)
    old_eta = await get_eta(ml_client, {"lat": amb_point.y, "lng": amb_point.x},
                             {"lat": old_hosp_point.y, "lng": old_hosp_point.x}, None)

    # Is there a candidate hospital that's genuinely faster? Reuse the same
    # candidate search selection uses, excluding the current hospital.
    candidates = await list_hospitals_within_km(db, amb_point.y, amb_point.x, radius_km=25.0)
    best_new_eta_sec = None
    for cand in candidates:
        if cand.id == current_hospital.id:
            continue
        cand_point = to_shape(cand.location)
        eta = await get_eta(ml_client, {"lat": amb_point.y, "lng": amb_point.x},
                             {"lat": cand_point.y, "lng": cand_point.x}, None)
        if best_new_eta_sec is None or eta["seconds"] < best_new_eta_sec:
            best_new_eta_sec = eta["seconds"]

    if best_new_eta_sec is not None and old_eta["seconds"] - best_new_eta_sec >= DETERIORATION_DIVERT_GAIN_SEC:
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
    """The previous version returned a hardcoded list of two fictional
    hospitals ("City General", "Mercy Care") regardless of the emergency --
    real candidates + real time deltas now, reusing the same candidate
    search and ETA lookup selection.py uses."""
    em = await db.get(Emergency, emergency_id)
    if not em or em.location is None:
        return []

    em_point = to_shape(em.location)
    facility = em.facility or "general"
    required_capability = FACILITY_TO_CAPABILITY.get(facility, "general_er")

    current_eta_sec = None
    if em.hospital_id:
        current_hospital = await db.get(Hospital, em.hospital_id)
        if current_hospital:
            h_point = to_shape(current_hospital.location)
            current = await get_eta(None, {"lat": em_point.y, "lng": em_point.x}, {"lat": h_point.y, "lng": h_point.x}, None)
            current_eta_sec = current["seconds"]

    candidates = await list_hospitals_within_km(db, em_point.y, em_point.x, radius_km=25.0)
    options = []
    for cand in candidates:
        cand_point = to_shape(cand.location)
        eta = await get_eta(None, {"lat": em_point.y, "lng": em_point.x}, {"lat": cand_point.y, "lng": cand_point.x}, None)
        time_delta_mins = (eta["seconds"] - current_eta_sec) / 60 if current_eta_sec is not None else 0
        capability_gaps = [] if required_capability in (cand.capabilities or []) else [required_capability]
        options.append({
            "hospital_id": str(cand.id), "name": cand.name,
            "time_delta_mins": round(time_delta_mins, 1),
            "capability_gaps": capability_gaps,
            "staleness": 0,
        })
    return options

async def apply_family_override(db: AsyncSession, emergency_id: UUID, hospital_id: UUID) -> None:
    from app.domain.reservations import create_hospital_request_with_hold
    em = await db.get(Emergency, emergency_id)
    acuity = (em.acuity if em else None) or "urgent"
    facility = (em.facility if em else None) or "general"
    await create_hospital_request_with_hold(
        db,
        emergency_id=emergency_id,
        hospital_id=hospital_id,
        rank=1,
        features={},
        explanation=["Family override requested"],
        acuity=acuity,
        facility=facility,
        is_family_choice=True
    )

async def handle_refused_transport(db: AsyncSession, emergency_id: UUID, note: str) -> None:
    em = await db.get(Emergency, emergency_id)
    if not em: return

    from app.domain.fsm.emergency_fsm import validate_transition
    validate_transition(em.status, "refused_transport")
    em.status = "refused_transport"

    if em.ambulance_id:
        # 'idle' is not a real AmbulanceStatus value (technical.md §3:
        # offline/available/dispatched/at_scene/transporting/at_hospital/
        # cleaning/out_of_service) -- the ambulance becomes available again.
        await db.execute(update(Ambulance).where(Ambulance.id == em.ambulance_id).values(status='available'))

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
        from app.domain.audit import write as audit_write
        # Real signature is keyword-only (actor_type, actor_id, entity,
        # entity_id, action, before, after) -- the previous positional call
        # `audit_write(db, "patient", temp_pat.id, merged_by, "merge", {...})`
        # would have raised TypeError the first time this ever ran.
        await audit_write(
            db, actor_type="user", actor_id=str(merged_by), entity="patients",
            entity_id=temp_pat.id, action="merge",
            before={"temp_id": temp_id, "is_unknown": True},
            after={"phone": phone, "is_unknown": False},
        )
        temp_pat.phone = phone
        temp_pat.is_unknown = False


# ---------------------------------------------------------------------------
# Aliases used by api/v1/clinical.py router
# ---------------------------------------------------------------------------

async def confirm_triage(
    db: AsyncSession,
    emergency_id: UUID,
    acuity: str,
    facility: str,
    patient_count: int,
    version: int,
    actor_id: UUID,
    ambulance_id: UUID,
) -> dict:
    """Confirm triage and trigger hospital selection.

    Had no ownership or FSM-state check at all -- any authenticated
    paramedic could confirm triage for ANY emergency regardless of whether
    they were assigned to it, and calling this before an ambulance was even
    assigned would still push the emergency all the way to
    'hospital_selecting' with ambulance_id still NULL (start_selection ->
    create_hospital_request_with_hold sets status unconditionally). Found by
    actually calling this out of the real UI's sequence and watching a
    hospital request get created for a case with no ambulance attached."""
    em = await db.get(Emergency, emergency_id)
    if not em:
        raise ValueError("Emergency not found")
    if not em.ambulance_id or str(em.ambulance_id) != str(ambulance_id):
        raise NotYourEmergency("not your emergency")
    if em.status not in ("at_scene", "patient_on_board", "hospital_selecting", "hospital_confirmed"):
        raise ValueError(f"Cannot confirm triage from status '{em.status}'")
    await handle_triage_change(db, emergency_id, acuity, facility, ml_client=None, redis_client=None)
    return {"acuity": acuity, "facility": facility, "patient_count": patient_count}


async def cancel_hospital_request_and_retry(
    db: AsyncSession, emergency_id: UUID, actor_id: UUID, ambulance_id: UUID,
) -> dict:
    """Paramedic-side 'this hospital isn't responding, try another one' --
    there was previously no way to move off a pending request except waiting
    for the hospital to actually accept/reject it, which blocked testing
    (and a real stuck case) completely."""
    from app.domain.reservations import cancel_hospital_request
    from app.db.repos.hospital_requests import get_pending_request_for_emergency

    em = await db.get(Emergency, emergency_id)
    if not em:
        raise ValueError("Emergency not found")
    if not em.ambulance_id or str(em.ambulance_id) != str(ambulance_id):
        raise NotYourEmergency("not your emergency")

    req = await get_pending_request_for_emergency(db, emergency_id)
    if not req:
        raise ValueError("No pending hospital request to cancel")

    await cancel_hospital_request(db, req.id, actor_id)
    await start_selection(db, None, None, emergency_id, trigger="cancelled_by_paramedic")
    return {"cancelled_request_id": str(req.id)}


async def trigger_critical_deterioration(
    db: AsyncSession,
    emergency_id: UUID,
    actor_id: UUID,
) -> None:
    """One-tap critical deterioration handler."""
    await handle_deterioration(db, emergency_id, ml_client=None, redis_client=None)


async def execute_family_override(
    db: AsyncSession,
    emergency_id: UUID,
    hospital_id: UUID,
    actor_id: UUID,
) -> None:
    """Execute a family-chosen hospital override."""
    await apply_family_override(db, emergency_id, hospital_id)


async def record_refused_transport(
    db: AsyncSession,
    emergency_id: UUID,
    note: str | None,
    actor_id: UUID,
) -> None:
    """Record that patient refused transport."""
    await handle_refused_transport(db, emergency_id, note or "")


class NotYourEmergency(Exception):
    pass


async def mark_arrived_scene(db: AsyncSession, emergency_id: UUID, ambulance_id: UUID, actor_id: UUID) -> dict:
    """POST /emergencies/{id}/arrived-scene -- frontend's job/[id]/page.tsx
    'arrive' button (ambulance_assigned -> at_scene, technical.md's own FSM
    transition graph, fsm/emergency_fsm.py). This route didn't exist at all
    on the real backend -- the button 404'd every time."""
    em = await db.get(Emergency, emergency_id)
    if not em:
        raise ValueError("Emergency not found")
    if str(em.ambulance_id) != str(ambulance_id):
        raise NotYourEmergency("not your emergency")
    if em.status != "ambulance_assigned":
        return {"status": em.status}  # already past this step -- idempotent no-op, not an error
    em.status = "at_scene"
    em.at_scene_at = datetime.utcnow()
    em.version += 1
    return {"status": em.status}


async def mark_arrived_hospital(db: AsyncSession, emergency_id: UUID, ambulance_id: UUID, actor_id: UUID) -> dict:
    """POST /emergencies/{id}/arrived-hospital -- same gap as arrived-scene
    above (hospital_confirmed -> arrived_hospital)."""
    em = await db.get(Emergency, emergency_id)
    if not em:
        raise ValueError("Emergency not found")
    if str(em.ambulance_id) != str(ambulance_id):
        raise NotYourEmergency("not your emergency")
    if em.status != "hospital_confirmed":
        return {"status": em.status}
    em.status = "arrived_hospital"
    em.arrived_hospital_at = datetime.utcnow()
    em.version += 1
    return {"status": em.status}
