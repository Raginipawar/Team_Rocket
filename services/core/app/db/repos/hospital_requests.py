"""Repository for hospital_requests (dispatch offers / inbound patient requests)."""
from uuid import UUID
from typing import Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.dispatch import HospitalRequest

# apps/web's RequestCard.tsx (HospitalRequestCard in lib/api-types.ts) reads
# req.request_id / req.patient.{acuity,facility,mlc_flag,confirmed_by_paramedic,
# display,temp_id} / req.ambulance.{registration_no,eta_sec} unconditionally --
# the old _to_dict only ever returned the bare hospital_requests row (id,
# status, rank, explanation...), so every one of those reads crashed with
# "Cannot read properties of undefined" the first time a real pending
# request was ever rendered. This joins in the patient/ambulance data the
# card actually needs; req.profile/handover_note/prep_checklist/why_you stay
# conditionally-rendered in the component so null/[] there is fine.
_CARD_COLUMNS = """
    hr.id, hr.emergency_id, hr.hospital_id, hr.status, hr.rank, hr.explanation,
    hr.is_family_choice, hr.is_priority, hr.expires_at, hr.created_at,
    res.room_id AS suggested_room_id,
    em.final_acuity, em.ai_acuity, em.final_facility, em.ai_facility, em.mlc_flag,
    em.eta_to_hospital_sec, em.eta_to_patient_sec, em.transcript, em.handover_note, em.predicted_resources,
    (em.photo_data IS NOT NULL) AS has_photo, em.photo_analysis,
    p.temp_id, p.est_age, p.sex,
    hp.blood_group, hp.allergies, hp.conditions, hp.medications,
    a.registration_no, a.type AS ambulance_type,
    ST_Y(a.current_location::geometry) AS amb_lat, ST_X(a.current_location::geometry) AS amb_lng,
    a.last_heartbeat_at
"""
_CARD_JOINS = """
    FROM hospital_requests hr
    JOIN emergencies em ON em.id = hr.emergency_id
    LEFT JOIN patients p ON p.emergency_id = em.id
    LEFT JOIN health_profiles hp ON hp.user_id = p.user_id
    LEFT JOIN ambulances a ON a.id = em.ambulance_id
    LEFT JOIN reservations res ON res.id = hr.reservation_id
"""


async def list_pending_requests(db: AsyncSession, hospital_id: UUID) -> list[dict]:
    """Return all pending hospital requests for a hospital."""
    rows = (await db.execute(
        text(f"SELECT {_CARD_COLUMNS} {_CARD_JOINS} "
             "WHERE hr.hospital_id = :hospital_id AND hr.status = 'pending' "
             "ORDER BY hr.created_at ASC"),
        {"hospital_id": hospital_id},
    )).mappings().all()
    return [_to_card_dict(r) for r in rows]


async def list_all_requests(
    db: AsyncSession,
    hospital_id: UUID,
    status: Optional[str] = None,
) -> list[dict]:
    """Return hospital requests filtered by optional status."""
    where = "WHERE hr.hospital_id = :hospital_id"
    params: dict = {"hospital_id": hospital_id}
    if status:
        where += " AND hr.status = :status"
        params["status"] = status
    rows = (await db.execute(
        text(f"SELECT {_CARD_COLUMNS} {_CARD_JOINS} {where} ORDER BY hr.created_at DESC"),
        params,
    )).mappings().all()
    return [_to_card_dict(r) for r in rows]


async def get_hospital_request(db: AsyncSession, request_id: UUID) -> Optional[HospitalRequest]:
    result = await db.execute(
        select(HospitalRequest).where(HospitalRequest.id == request_id)
    )
    return result.scalar_one_or_none()


async def get_pending_request_for_emergency(db: AsyncSession, emergency_id: UUID) -> Optional[HospitalRequest]:
    result = await db.execute(
        select(HospitalRequest).where(HospitalRequest.emergency_id == emergency_id, HospitalRequest.status == "pending")
    )
    return result.scalar_one_or_none()


async def list_attempted_hospital_ids(db: AsyncSession, emergency_id: UUID) -> list[UUID]:
    """Hospitals already offered this emergency (any status) -- so a re-run of
    selection (after a cancel/reject/timeout) picks a different candidate
    instead of immediately re-offering the same one with nothing changed."""
    result = await db.execute(
        select(HospitalRequest.hospital_id).where(HospitalRequest.emergency_id == emergency_id)
    )
    return [row[0] for row in result.all()]


async def list_incoming_ambulances(db: AsyncSession, hospital_id: UUID, *, at_door: bool) -> list[dict]:
    """apps/web's hospital dashboard (app/hospital/page.tsx) reads
    dashboard.incoming/dashboard.at_door (IncomingAmbulance[] in
    lib/api-types.ts) -- neither existed anywhere in get_dashboard's real
    response, so "Incoming" always showed empty even for a hospital that had
    just accepted a request. Status filter matches the real FSM
    (fsm/emergency_fsm.py): hospital_confirmed = on the way,
    arrived_hospital = at the door waiting to be received."""
    status = "arrived_hospital" if at_door else "hospital_confirmed"
    rows = (await db.execute(
        text(f"""
            SELECT em.id AS emergency_id, em.final_acuity, em.ai_acuity, em.final_facility, em.ai_facility,
                   em.eta_to_hospital_sec, em.arrived_hospital_at,
                   a.registration_no, a.type AS ambulance_type, a.last_heartbeat_at,
                   ST_Y(a.current_location::geometry) AS amb_lat, ST_X(a.current_location::geometry) AS amb_lng,
                   p.temp_id, p.est_age, p.sex,
                   r.code AS room_code
            FROM emergencies em
            LEFT JOIN ambulances a ON a.id = em.ambulance_id
            LEFT JOIN patients p ON p.emergency_id = em.id
            LEFT JOIN reservations res ON res.emergency_id = em.id AND res.status IN ('confirmed', 'held')
            LEFT JOIN rooms r ON r.id = res.room_id
            WHERE em.hospital_id = :hospital_id AND em.status = :status
            ORDER BY em.hospital_confirmed_at ASC NULLS LAST
        """),
        {"hospital_id": hospital_id, "status": status},
    )).mappings().all()
    return [_to_incoming_dict(r) for r in rows]


def _to_incoming_dict(r) -> dict:
    sex_label = {"M": "Male", "F": "Female"}.get(r["sex"] or "", "Unknown")
    display = f"{sex_label}, ~{r['est_age']}" if r["est_age"] else sex_label
    return {
        "emergency_id": str(r["emergency_id"]),
        "registration_no": r["registration_no"] or "",
        "type": r["ambulance_type"],
        "acuity": r["final_acuity"] or r["ai_acuity"] or "urgent",
        "facility": r["final_facility"] or r["ai_facility"] or "general",
        "location": {"lat": r["amb_lat"], "lng": r["amb_lng"]} if r["amb_lat"] is not None else None,
        "eta_sec": r["eta_to_hospital_sec"],
        "eta_low_sec": None,
        "eta_high_sec": None,
        "signal": _signal(r["last_heartbeat_at"]),
        "last_seen_at": r["last_heartbeat_at"].isoformat() if r["last_heartbeat_at"] else None,
        "room_code": r["room_code"],
        "patient_display": display,
        "arrived_at": r["arrived_hospital_at"].isoformat() if r["arrived_hospital_at"] else None,
        "temp_id": r["temp_id"],
    }


def _signal(last_heartbeat_at) -> str:
    if not last_heartbeat_at:
        return "lost"
    from datetime import datetime, timezone
    age_sec = (datetime.now(timezone.utc) - last_heartbeat_at).total_seconds()
    if age_sec < 30:
        return "ok"
    if age_sec < 120:
        return "weak"
    return "lost"


def _to_card_dict(r) -> dict:
    sex_label = {"M": "Male", "F": "Female"}.get(r["sex"] or "", "Unknown")
    display = f"{sex_label}, ~{r['est_age']}" if r["est_age"] else sex_label
    eta_sec = r["eta_to_hospital_sec"] if r["eta_to_hospital_sec"] is not None else r["eta_to_patient_sec"]
    return {
        "request_id": str(r["id"]),
        "emergency_id": str(r["emergency_id"]),
        "hospital_id": str(r["hospital_id"]),
        "status": r["status"],
        "rank": r["rank"],
        "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "is_family_choice": r["is_family_choice"],
        "is_priority": r["is_priority"],
        "suggested_room_id": str(r["suggested_room_id"]) if r["suggested_room_id"] else None,
        "suggested_staff_ids": [],
        "has_photo": bool(r["has_photo"]),
        "photo_analysis": r["photo_analysis"],
        "patient": {
            "display": display,
            "temp_id": r["temp_id"],
            "acuity": r["final_acuity"] or r["ai_acuity"] or "urgent",
            "facility": r["final_facility"] or r["ai_facility"] or "general",
            "confirmed_by_paramedic": bool(r["final_acuity"]),
            "mlc_flag": bool(r["mlc_flag"]),
        },
        "profile": (
            {
                "blood_group": r["blood_group"],
                "allergies": r["allergies"] or [],
                "conditions": r["conditions"] or [],
                "medications": r["medications"] or [],
            }
            if r["blood_group"] or r["allergies"] or r["conditions"] or r["medications"]
            else None
        ),
        "handover_note": r["handover_note"],
        # predicted_resources was computed by intake.py's own ml.resources()
        # call and stored on the row the whole time -- this was always
        # hardcoded to [] here, so the hospital's "Prepare" checklist never
        # showed anything a real prediction had produced, for any emergency,
        # ever. ResourceItem's own shape ({item, prob}) already matches
        # what RequestCard.tsx reads.
        "prep_checklist": (r["predicted_resources"] or {}).get("resources", []) if isinstance(r["predicted_resources"], dict) else [],
        "ambulance": {
            "registration_no": r["registration_no"] or "",
            "type": r["ambulance_type"],
            "location": {"lat": r["amb_lat"], "lng": r["amb_lng"]} if r["amb_lat"] is not None else None,
            "eta_sec": eta_sec,
            "eta_low_sec": None,
            "eta_high_sec": None,
            "signal": _signal(r["last_heartbeat_at"]),
        },
        "why_you": r["explanation"] if isinstance(r["explanation"], list) else ([r["explanation"]] if r["explanation"] else []),
    }
