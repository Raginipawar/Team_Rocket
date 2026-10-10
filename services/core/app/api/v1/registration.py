"""Real hospital self-registration. Didn't exist anywhere -- every
hospital_staff account was seed data (data/seed/seed.py), so there was no
way for a real hospital to actually sign up. Creates the real hospital
org record AND its first staff login in one transaction, then logs them
straight in (same pattern as patient OTP verify) -- no approval wait, per
explicit spec decision: automatic dashboard access, demo_mode distinguishes
"signed up" from "independently verified for real dispatch" without a
separate review workflow blocking the demo.

(Ambulance registration used to live here too -- superseded by the real
OTP-first flow in api/v1/ambulance.py register/register-demo, which ties
registration to an already-authenticated phone, not a password set at
registration time. Removed here to avoid two different ambulance signup
paths existing at once.)

Scope note (deliberate, not an oversight): we don't own bed/resource
tracking -- that's the hospital's own job -- we only allocate. So
registration creates real room/resource ROWS (so the hospital's own
dashboard, PATCH /hospital/rooms, PATCH /hospital/resources -- both
already real -- has something to edit), not a live integration with
whatever system the hospital already uses for that. A real HMS push/pull
API is a legitimate v2, not a same-day build -- integration_mode is
captured now so that's a config flip later, not a schema change."""
import random
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.session import get_session
from app.domain import audit
from app.security.jwt import create_access_token, create_refresh_token
from app.security.passwords import hash_password

router = APIRouter()

ROOM_TYPES = ["er_bed", "resus_bay", "trauma_bay", "icu_bed", "labour_room", "burns_unit", "pediatric_er"]
RESOURCE_TYPES = [
    "ventilator", "cath_lab", "ct_scanner", "mri", "defibrillator", "blood_o_neg",
    "blood_o_pos", "blood_a_pos", "blood_b_pos", "blood_ab_pos", "dialysis", "operating_theatre",
]
CAPABILITIES = [
    "cardiac_cathlab", "stroke_thrombolysis", "trauma_center", "burns_unit", "obstetrics",
    "pediatrics", "toxicology", "icu", "general_er",
]


class RoomCount(BaseModel):
    type: str
    count: int = Field(ge=0, le=100)


class HospitalRegisterRequest(BaseModel):
    hospital_name: str
    address: str
    lat: float
    lng: float
    capabilities: list[str]
    duty_manager_phone: str
    er_entrance_note: str | None = None
    staff_name: str
    staff_phone: str
    staff_password: str = Field(min_length=8)
    rooms: list[RoomCount] = []
    integration_mode: str = "manual"  # "manual" | "api" -- Data Integration section's choice


def _generate_hospital_code() -> str:
    return f"HSP-{random.randint(100000, 999999)}"


@router.post("/auth/register-hospital", status_code=201)
async def register_hospital(payload: HospitalRegisterRequest) -> dict:
    bad_caps = [c for c in payload.capabilities if c not in CAPABILITIES]
    if bad_caps:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": f"Unknown capabilities: {bad_caps}", "details": {}}})
    bad_rooms = [r.type for r in payload.rooms if r.type not in ROOM_TYPES]
    if bad_rooms:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": f"Unknown room types: {bad_rooms}", "details": {}}})
    if payload.integration_mode not in ("manual", "api"):
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "integration_mode must be manual or api", "details": {}}})

    async with get_session() as session:
        existing = (await session.execute(
            text("SELECT id FROM users WHERE phone = :phone AND role = 'hospital_staff'"), {"phone": payload.staff_phone}
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(409, detail={"error": {"code": "ALREADY_EXISTS", "message": "A hospital staff account with this phone already exists", "details": {}}})

        hospital_code = None
        for _ in range(10):
            candidate = _generate_hospital_code()
            dup = (await session.execute(
                text("SELECT 1 FROM hospitals WHERE hospital_code = :c"), {"c": candidate},
            )).scalar_one_or_none()
            if not dup:
                hospital_code = candidate
                break
        if not hospital_code:
            raise HTTPException(500, detail={"error": {"code": "INTERNAL_ERROR", "message": "Could not allocate a hospital code", "details": {}}})

        hospital_id = (await session.execute(
            text("""
                INSERT INTO hospitals (name, address, location, er_entrance_note, duty_manager_phone,
                                        capabilities, is_active, is_simulated, integration_mode, hospital_code)
                VALUES (:name, :address, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :er_entrance_note, :duty_manager_phone, :capabilities, true, false, :integration_mode, :code)
                RETURNING id
            """),
            {
                "name": payload.hospital_name, "address": payload.address, "lng": payload.lng, "lat": payload.lat,
                "er_entrance_note": payload.er_entrance_note, "duty_manager_phone": payload.duty_manager_phone,
                "capabilities": payload.capabilities, "integration_mode": payload.integration_mode, "code": hospital_code,
            },
        )).scalar_one()

        # Real resource rows for every type the system knows about, starting
        # at zero -- the hospital's own dashboard (already real) is how they
        # report actual counts; registration doesn't guess numbers for them.
        for rtype in RESOURCE_TYPES:
            await session.execute(
                text("INSERT INTO hospital_resources (hospital_id, type, total, available, reported_at) "
                     "VALUES (:hid, :type, 0, 0, now())"),
                {"hid": hospital_id, "type": rtype},
            )

        room_counter = 0
        for room_spec in payload.rooms:
            prefix = room_spec.type[:2].upper()
            for i in range(room_spec.count):
                room_counter += 1
                code = f"{prefix}-{room_counter}"
                await session.execute(
                    text("INSERT INTO rooms (hospital_id, code, type, status, priority_order) "
                         "VALUES (:hid, :code, :type, 'free', :priority)"),
                    {"hid": hospital_id, "code": code, "type": room_spec.type, "priority": room_counter},
                )

        password_hash = hash_password(payload.staff_password)
        user_row = (await session.execute(
            text("""
                INSERT INTO users (role, name, phone, password_hash, hospital_id, is_active)
                VALUES ('hospital_staff', :name, :phone, :password_hash, :hospital_id, true)
                RETURNING id, role, name, phone, hospital_id
            """),
            {"name": payload.staff_name, "phone": payload.staff_phone, "password_hash": password_hash, "hospital_id": hospital_id},
        )).mappings().first()

        await audit.write(
            session, actor_type="user", actor_id=str(user_row["id"]), entity="hospitals",
            entity_id=hospital_id, action="register", before=None,
            after={"name": payload.hospital_name, "staff_phone": payload.staff_phone, "hospital_code": hospital_code},
        )
        await session.commit()

    access = create_access_token(sub=str(user_row["id"]), role="hospital_staff", hospital_id=str(hospital_id))
    refresh = create_refresh_token(sub=str(user_row["id"]), role="hospital_staff")
    return {
        "access_token": access, "refresh_token": refresh,
        "hospital_id": str(hospital_id), "hospital_code": hospital_code,
        "user": {"id": str(user_row["id"]), "role": "hospital_staff", "name": user_row["name"],
                  "phone": user_row["phone"], "hospital_id": str(hospital_id)},
    }
