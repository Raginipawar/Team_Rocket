"""A's file (work-distribution.md §2.2). technical.md §7.4."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.db.repos import dispatch as dispatch_repo
from app.db.session import get_session
from app.domain import dispatch, lifecycle
from app.security.deps import CurrentUser, require_role

router = APIRouter()


@router.get("/me")
async def get_self(user: CurrentUser = Depends(require_role("paramedic"))) -> dict:
    # Frontend's lib/ambulance.ts fetchSelf() -- the ambulance home screen
    # (app/ambulance/page.tsx) blocks on this with no fallback ("if (!self)
    # return <LoadingState />"), so without this route the app never gets
    # past a spinner no matter what the rest of the stack does.
    if not user.ambulance_id:
        raise HTTPException(403, "user has no assigned ambulance")
    async with get_session() as session:
        row = (await session.execute(text("""
            SELECT id, registration_no, type, status, version, kyc_verified, is_simulated,
                   ST_Y(current_location::geometry) AS lat, ST_X(current_location::geometry) AS lng
            FROM ambulances WHERE id = :id
        """), {"id": user.ambulance_id})).mappings().first()
    if not row:
        raise HTTPException(404, "ambulance not found")
    return {
        "id": str(row["id"]), "registration_no": row["registration_no"], "type": row["type"],
        "status": row["status"], "version": row["version"], "kyc_verified": row["kyc_verified"],
        "is_simulated": row["is_simulated"],
        "location": {"lat": row["lat"], "lng": row["lng"]} if row["lat"] is not None else None,
    }


@router.get("/offers")
async def get_offers(user: CurrentUser = Depends(require_role("paramedic"))) -> list[dict]:
    if not user.ambulance_id:
        raise HTTPException(403, "user has no assigned ambulance")
    async with get_session() as session:
        return await dispatch_repo.list_pending_offers(session, user.ambulance_id)


@router.get("/active")
async def get_active_job(user: CurrentUser = Depends(require_role("paramedic"))) -> dict | None:
    """GET /ambulance/active (lib/ambulance.ts fetchActive()). Populates the
    fields the job screen (app/ambulance/job/[id]/page.tsx) actually reads;
    route/turns/destination/hospital_selecting stay null until routing +
    hospital-selection are wired into this payload (documented gap, not a
    silent omission)."""
    if not user.ambulance_id:
        raise HTTPException(403, "user has no assigned ambulance")
    async with get_session() as session:
        amb = (await session.execute(
            text("SELECT active_emergency_id FROM ambulances WHERE id = :id"), {"id": user.ambulance_id}
        )).mappings().first()
        if not amb or not amb["active_emergency_id"]:
            return None

        from app.db.repos.emergencies import get_emergency
        em = await get_emergency(session, str(amb["active_emergency_id"]))
        if not em or em["status"] in ("handed_off", "cancelled", "closed"):
            return None

        patient = (await session.execute(
            text("SELECT temp_id, est_age, sex FROM patients WHERE emergency_id = :id"),
            {"id": em["id"]},
        )).mappings().first()

    leg = "to_hospital" if em["status"] in (
        "on_board", "hospital_selecting", "hospital_confirmed", "arrived_hospital",
    ) else "to_patient"

    sex_label = {"M": "Male", "F": "Female"}.get((patient or {}).get("sex") or "", "Unknown")
    age = (patient or {}).get("est_age")
    display = f"{sex_label}, ~{age}" if age else f"{sex_label}"

    return {
        "emergency_id": str(em["id"]),
        "short_id": str(em["id"])[:8].upper(),
        "status": em["status"],
        "version": em["version"],
        "leg": leg,
        "pickup": {
            "lat": em.get("lat"), "lng": em.get("lng"),
            "landmark": em.get("landmark_text"), "accuracy_m": em.get("location_accuracy_m"),
        },
        "caller_phone": em.get("caller_phone"),
        "patient": {
            "display": display, "temp_id": (patient or {}).get("temp_id"),
            "age": age, "sex": (patient or {}).get("sex"), "patient_count": 1,
            "profile": None,
        },
        "triage": {
            "acuity": em.get("final_acuity") or em.get("ai_acuity") or "urgent",
            "facility": em.get("final_facility") or em.get("ai_facility") or "general",
            "confidence": em.get("ai_confidence") or 0,
            "confirmed": bool(em.get("final_acuity")),
            "needs_review": em.get("needs_review"),
            "ai_acuity": em.get("ai_acuity"), "ai_facility": em.get("ai_facility"),
            "mlc_flag": em.get("mlc_flag"), "fragility": em.get("fragility"),
        },
        "transcript": em.get("transcript"),
        "route": None, "eta_sec": em.get("eta_to_patient_sec") if leg == "to_patient" else em.get("eta_to_hospital_sec"),
        "distance_m": None, "turns": None,
        "destination": None, "hospital_selecting": None, "arrived_at": None,
    }


class HeartbeatRequest(BaseModel):
    lat: float
    lng: float
    heading: float | None = None
    speed_kmh: float | None = None
    accuracy_m: float | None = None
    client_ts: str | None = None


class StatusRequest(BaseModel):
    status: str  # available | offline | cleaning_done
    version: int


@router.post("/heartbeat", status_code=204)
async def heartbeat(req: HeartbeatRequest, user: CurrentUser = Depends(require_role("paramedic"))) -> None:
    if not user.ambulance_id:
        raise HTTPException(403, "user has no assigned ambulance")
    async with get_session() as session:
        await lifecycle.record_heartbeat(
            session, ambulance_id=user.ambulance_id, lat=req.lat, lng=req.lng,
            heading=req.heading, speed_kmh=req.speed_kmh,
        )
        await session.commit()


@router.post("/status")
async def set_status(req: StatusRequest, user: CurrentUser = Depends(require_role("paramedic"))) -> dict:
    if not user.ambulance_id:
        raise HTTPException(403, "user has no assigned ambulance")
    if req.status not in ("available", "offline", "cleaning_done"):
        raise HTTPException(400, "invalid status")

    async with get_session() as session:
        try:
            result = await lifecycle.set_ambulance_status(
                session, ambulance_id=user.ambulance_id, new_status=req.status, expected_version=req.version,
            )
        except lifecycle.VersionConflict:
            await session.rollback()
            raise HTTPException(409, detail={"error": {"code": "VERSION_CONFLICT", "message": "Ambulance was modified", "details": {}}})
        await session.commit()
    return result


@router.post("/vehicle-issue", status_code=204)
async def vehicle_issue(user: CurrentUser = Depends(require_role("paramedic"))) -> None:
    if not user.ambulance_id:
        raise HTTPException(403, "user has no assigned ambulance")
    async with get_session() as session:
        await dispatch.handle_vehicle_issue(session, ambulance_id=user.ambulance_id)
        await session.commit()
