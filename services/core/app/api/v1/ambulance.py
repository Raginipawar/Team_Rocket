"""A's file (work-distribution.md §2.2). technical.md §7.4."""

import json
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sqlalchemy import text

from app.db.repos import dispatch as dispatch_repo
from app.db.repos.hospital_requests import get_pending_request_for_emergency
from app.db.session import get_session
from app.domain import dispatch, lifecycle
from app.integrations.ml.routing import get_route
from app.security.deps import CurrentUser, require_role
from app.security.jwt import create_access_token

router = APIRouter()

CAPABILITIES = ["general", "cardiac", "trauma", "pediatric", "ventilator"]
EQUIPMENT = ["oxygen", "aed", "monitor", "ventilator", "suction", "stretcher"]
AMBULANCE_CATEGORIES = ["A", "B", "C", "D"]  # AIS-125 categories


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

        amb_loc = (await session.execute(
            text("SELECT ST_Y(current_location::geometry) AS lat, ST_X(current_location::geometry) AS lng "
                 "FROM ambulances WHERE id = :id"), {"id": user.ambulance_id},
        )).mappings().first()

        leg = "to_hospital" if em["status"] in (
            "on_board", "hospital_selecting", "hospital_confirmed", "arrived_hospital",
        ) else "to_patient"

        # ActiveJob.destination is the hospital-arrival shape (HospitalView +
        # room/team info) -- the pickup leg already has its own `pickup`
        # field/map prop for that pin, so destination stays null until
        # there's a real hospital to show, matching the existing contract
        # rather than overloading the field with a second shape.
        destination = None
        route_target = None
        if leg == "to_patient" and em.get("lat") is not None:
            route_target = {"lat": em["lat"], "lng": em["lng"]}
        elif leg == "to_hospital" and em.get("hospital_id"):
            hosp = (await session.execute(
                text("SELECT name, er_entrance_note, duty_manager_phone, "
                     "ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng "
                     "FROM hospitals WHERE id = :id"), {"id": em["hospital_id"]},
            )).mappings().first()
            if hosp:
                route_target = {"lat": hosp["lat"], "lng": hosp["lng"]}
                destination = {
                    "hospital": {
                        "name": hosp["name"], "location": {"lat": hosp["lat"], "lng": hosp["lng"]},
                        "er_entrance_note": hosp["er_entrance_note"], "phone": hosp["duty_manager_phone"],
                    },
                    "entrance_note": hosp["er_entrance_note"],
                }

        # Real turn-by-turn only when both ends are actually known (live
        # ambulance GPS fix + a real destination) -- no fallback straight
        # line pretending to be a route.
        route_data = None
        if amb_loc and amb_loc["lat"] is not None and route_target:
            route_data = await get_route(
                None, {"lat": amb_loc["lat"], "lng": amb_loc["lng"]}, route_target,
            )

        hospital_selecting = None
        if em["status"] == "hospital_selecting":
            pending = await get_pending_request_for_emergency(session, em["id"])
            if pending:
                hname = (await session.execute(
                    text("SELECT name FROM hospitals WHERE id = :id"), {"id": pending.hospital_id},
                )).scalar_one_or_none()
                hospital_selecting = {"hospital_name": hname}

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
        "route": route_data.get("geometry") if route_data else None,
        # Real route's own eta_sec takes priority over the stored
        # eta_to_patient/hospital_sec columns (set once at an earlier dispatch
        # step, not kept live) -- this is the live ETA for right now, not a
        # stale snapshot from whenever the emergency was first dispatched.
        "eta_sec": (route_data.get("eta_sec") if route_data else None)
                   or (em.get("eta_to_patient_sec") if leg == "to_patient" else em.get("eta_to_hospital_sec")),
        "distance_m": route_data.get("distance_m") if route_data else None,
        "turns": [t["instruction"] for t in route_data["turns"]] if route_data and route_data.get("turns") else None,
        "route_explanation": route_data.get("explanation") if route_data else None,
        "destination": destination, "hospital_selecting": hospital_selecting, "arrived_at": None,
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


class RegisterRequest(BaseModel):
    # Section A -- operator
    operator_name: str
    email: str | None = None
    organisation: str | None = None
    # Section B -- vehicle
    registration_no: str
    make_model: str
    category: str  # AIS-125 A/B/C/D
    year: int | None = None
    operating_area: str
    base_location: str
    # Section C -- capabilities (clinical matching, not just a label)
    capabilities: list[str] = []
    equipment: list[str] = []
    # Section D -- authorisation info (numbers/dates only, no file upload --
    # the team verifies supporting documents separately, the form just
    # captures what they need to review)
    driver_license_no: str
    crew_details: str | None = None
    rc_number: str | None = None
    insurance_number: str | None = None
    permit_number: str | None = None
    declaration_confirmed: bool = Field(..., description="Section E declaration checkbox")


def _validate_registration(payload: "RegisterRequest") -> None:
    if payload.category not in AMBULANCE_CATEGORIES:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": f"category must be one of {AMBULANCE_CATEGORIES}", "details": {}}})
    bad_caps = [c for c in payload.capabilities if c not in CAPABILITIES]
    if bad_caps:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": f"unknown capabilities: {bad_caps}", "details": {}}})
    bad_eq = [e for e in payload.equipment if e not in EQUIPMENT]
    if bad_eq:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": f"unknown equipment: {bad_eq}", "details": {}}})
    if not payload.declaration_confirmed:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "declaration must be confirmed", "details": {}}})


@router.post("/register", status_code=201)
async def register_live(payload: RegisterRequest, user: CurrentUser = Depends(require_role("paramedic"))) -> dict:
    """Live registration: real operator/vehicle info, submitted for the
    team's review -- NOT auto-approved. kyc_verified stays false (the real
    dispatch-eligibility gate, db/repos/ambulances.py find_candidates)
    until someone on the ops side reviews and approves it. A phone OTP
    verifies the phone, nothing else -- this is the "nothing else" part."""
    if user.ambulance_id:
        raise HTTPException(409, detail={"error": {"code": "ALREADY_REGISTERED", "message": "This account already has a registered ambulance", "details": {}}})
    _validate_registration(payload)

    async with get_session() as session:
        existing = (await session.execute(
            text("SELECT id FROM ambulances WHERE registration_no = :reg"), {"reg": payload.registration_no},
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(409, detail={"error": {"code": "ALREADY_EXISTS", "message": "This registration number is already registered", "details": {}}})

        reg_data = payload.model_dump(exclude={"capabilities", "equipment", "registration_no", "category"})
        ambulance_id = (await session.execute(
            text("""
                INSERT INTO ambulances (registration_no, type, equipment, status, driver_license_no,
                                         kyc_verified, is_simulated, registration_status, registration_data, capabilities)
                VALUES (:reg, :type, :equipment, 'offline', :license, false, false, 'pending', CAST(:data AS jsonb), :caps)
                RETURNING id
            """),
            {
                "reg": payload.registration_no, "type": "ALS" if "cardiac" in payload.capabilities else "BLS",
                "equipment": payload.equipment, "license": payload.driver_license_no,
                "data": json.dumps({**reg_data, "category": payload.category}, default=str),
                "caps": payload.capabilities,
            },
        )).scalar_one()
        await session.execute(
            text("UPDATE users SET ambulance_id = :aid, name = COALESCE(name, :name) WHERE id = :uid"),
            {"aid": ambulance_id, "name": payload.operator_name, "uid": user.id},
        )
        await session.commit()
    # A fresh access token with the new ambulance_id claim -- the old one
    # (still carrying ambulance_id: null) stays valid until its own natural
    # expiry/refresh, which would otherwise leave the app unable to use
    # ambulance-scoped routes immediately after a successful registration.
    access = create_access_token(sub=user.id, role="paramedic", ambulance_id=str(ambulance_id))
    return {"ambulance_id": str(ambulance_id), "registration_status": "pending", "access_token": access}


_DEMO_NAMES = ["Demo Operator", "Demo Fleet Services"]


@router.post("/register/demo", status_code=201)
async def register_demo(user: CurrentUser = Depends(require_role("paramedic"))) -> dict:
    """Demo registration: auto-fills and submits instantly, kyc_verified=true
    right away (no real review -- that's the point of Demo). registration_no
    is deliberately plate-shaped (MH12AB####), not DEMO-AMB-#### -- the old
    literal "DEMO" prefix was the whole point internally but read badly on
    screen during a live demo. "Is this a demo ambulance" is still tracked
    for real via is_simulated=true below, which the rest of the system
    (dispatch/tracking/ops) already keys off of -- nothing depends on the
    registration_no string itself, so this is purely cosmetic. Still goes
    through the exact same real dispatch pipeline as every other ambulance
    in this system -- "demo" here means "skipped the approval wait", not
    "fake backend"."""
    if user.ambulance_id:
        raise HTTPException(409, detail={"error": {"code": "ALREADY_REGISTERED", "message": "This account already has a registered ambulance", "details": {}}})

    suffix = f"{random.randint(1000, 9999)}"
    reg_no = f"MH12AB{suffix}"
    caps = ["general", "cardiac"]
    equipment = ["oxygen", "aed", "monitor", "stretcher"]
    demo_data = {
        "operator_name": "Demo Operator", "organisation": "Demo Fleet Services",
        "make_model": "Force Traveller (Demo)", "operating_area": "Pune Demo Zone",
        "base_location": "Demo Base Station", "driver_license_no": f"DEMO-DL-{suffix}",
        "crew_details": "Demo crew (preconfigured)", "category": "B",
    }

    async with get_session() as session:
        ambulance_id = (await session.execute(
            text("""
                INSERT INTO ambulances (registration_no, type, equipment, status, driver_license_no,
                                         kyc_verified, is_simulated, registration_status, registration_data, capabilities)
                VALUES (:reg, 'ALS', :equipment, 'offline', :license, true, true, 'demo', CAST(:data AS jsonb), :caps)
                RETURNING id
            """),
            {
                "reg": reg_no, "equipment": equipment, "license": demo_data["driver_license_no"],
                "data": json.dumps(demo_data), "caps": caps,
            },
        )).scalar_one()
        await session.execute(
            text("UPDATE users SET ambulance_id = :aid, name = COALESCE(name, 'Demo Operator') WHERE id = :uid"),
            {"aid": ambulance_id, "uid": user.id},
        )
        await session.commit()
    access = create_access_token(sub=user.id, role="paramedic", ambulance_id=str(ambulance_id))
    return {"ambulance_id": str(ambulance_id), "registration_status": "demo", "registration_no": reg_no, "access_token": access}


@router.get("/registration-status")
async def registration_status(user: CurrentUser = Depends(require_role("paramedic"))) -> dict:
    if not user.ambulance_id:
        return {"status": None, "ambulance_id": None}
    async with get_session() as session:
        row = (await session.execute(
            text("SELECT registration_status, rejection_reason, registration_no FROM ambulances WHERE id = :id"),
            {"id": user.ambulance_id},
        )).mappings().first()
    if not row:
        return {"status": None, "ambulance_id": None}
    return {
        "status": row["registration_status"], "ambulance_id": user.ambulance_id,
        "registration_no": row["registration_no"], "rejection_reason": row["rejection_reason"],
    }
