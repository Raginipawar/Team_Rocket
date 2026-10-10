"""Real hospital and ambulance self-registration. Didn't exist anywhere --
every hospital_staff/paramedic account was seed data (data/seed/seed.py),
so there was no way for a real hospital or a real ambulance crew to
actually sign up. Each registration creates the real org record (hospital
or ambulance) AND its first staff/paramedic login in one transaction, then
logs them straight in (same pattern as patient OTP verify) so there's no
separate "wait for an email" step.

Scope note (deliberate, not an oversight): we don't own bed/resource
tracking -- that's the hospital's own job -- we only allocate. So
registration creates real room/resource ROWS (so the hospital's own
dashboard, PATCH /hospital/rooms, PATCH /hospital/resources -- both
already real -- has something to edit), not a live integration with
whatever system the hospital already uses for that. A real HMS push/pull
API is a legitimate v2, not a same-day build."""
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


class AmbulanceRegisterRequest(BaseModel):
    registration_no: str
    type: str  # ALS | BLS
    equipment: list[str] = []
    driver_license_no: str
    paramedic_name: str
    paramedic_phone: str
    paramedic_password: str = Field(min_length=8)


def _issue_tokens_for(user: dict) -> str:
    return create_access_token(
        sub=str(user["id"]), role=user["role"],
        hospital_id=str(user.get("hospital_id")) if user.get("hospital_id") else None,
        ambulance_id=str(user.get("ambulance_id")) if user.get("ambulance_id") else None,
    )


@router.post("/auth/register-hospital", status_code=201)
async def register_hospital(payload: HospitalRegisterRequest) -> dict:
    bad_caps = [c for c in payload.capabilities if c not in CAPABILITIES]
    if bad_caps:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": f"Unknown capabilities: {bad_caps}", "details": {}}})
    bad_rooms = [r.type for r in payload.rooms if r.type not in ROOM_TYPES]
    if bad_rooms:
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": f"Unknown room types: {bad_rooms}", "details": {}}})

    async with get_session() as session:
        existing = (await session.execute(
            text("SELECT id FROM users WHERE phone = :phone"), {"phone": payload.staff_phone}
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(409, detail={"error": {"code": "ALREADY_EXISTS", "message": "A user with this phone already exists", "details": {}}})

        hospital_id = (await session.execute(
            text("""
                INSERT INTO hospitals (name, address, location, er_entrance_note, duty_manager_phone,
                                        capabilities, is_active, is_simulated)
                VALUES (:name, :address, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :er_entrance_note, :duty_manager_phone, :capabilities, true, false)
                RETURNING id
            """),
            {
                "name": payload.hospital_name, "address": payload.address, "lng": payload.lng, "lat": payload.lat,
                "er_entrance_note": payload.er_entrance_note, "duty_manager_phone": payload.duty_manager_phone,
                "capabilities": payload.capabilities,
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
            after={"name": payload.hospital_name, "staff_phone": payload.staff_phone},
        )
        await session.commit()

    user = dict(user_row)
    access = _issue_tokens_for(user)
    refresh = create_refresh_token(sub=str(user["id"]), role="hospital_staff")
    return {
        "access_token": access, "refresh_token": refresh,
        "hospital_id": str(hospital_id),
        "user": {"id": str(user["id"]), "role": "hospital_staff", "name": user["name"],
                  "phone": user["phone"], "hospital_id": str(hospital_id)},
    }


@router.post("/auth/register-ambulance", status_code=201)
async def register_ambulance(payload: AmbulanceRegisterRequest) -> dict:
    if payload.type not in ("ALS", "BLS"):
        raise HTTPException(400, detail={"error": {"code": "VALIDATION_ERROR", "message": "type must be ALS or BLS", "details": {}}})

    async with get_session() as session:
        existing_user = (await session.execute(
            text("SELECT id FROM users WHERE phone = :phone"), {"phone": payload.paramedic_phone}
        )).scalar_one_or_none()
        if existing_user:
            raise HTTPException(409, detail={"error": {"code": "ALREADY_EXISTS", "message": "A user with this phone already exists", "details": {}}})
        existing_amb = (await session.execute(
            text("SELECT id FROM ambulances WHERE registration_no = :reg"), {"reg": payload.registration_no}
        )).scalar_one_or_none()
        if existing_amb:
            raise HTTPException(409, detail={"error": {"code": "ALREADY_EXISTS", "message": "This registration number is already registered", "details": {}}})

        # kyc_verified stays the real default (false) -- a self-registered
        # ambulance cannot be dispatched to (db/repos/ambulances.py's
        # find_candidates filters on it) until an ops/admin operator
        # verifies the license, matching real EMS compliance expectations,
        # not silently granting trust on signup.
        ambulance_id = (await session.execute(
            text("""
                INSERT INTO ambulances (registration_no, type, equipment, status, driver_license_no,
                                         kyc_verified, is_simulated)
                VALUES (:reg, :type, :equipment, 'offline', :license, false, false)
                RETURNING id
            """),
            {"reg": payload.registration_no, "type": payload.type, "equipment": payload.equipment,
             "license": payload.driver_license_no},
        )).scalar_one()

        password_hash = hash_password(payload.paramedic_password)
        user_row = (await session.execute(
            text("""
                INSERT INTO users (role, name, phone, password_hash, ambulance_id, is_active)
                VALUES ('paramedic', :name, :phone, :password_hash, :ambulance_id, true)
                RETURNING id, role, name, phone, ambulance_id
            """),
            {"name": payload.paramedic_name, "phone": payload.paramedic_phone, "password_hash": password_hash, "ambulance_id": ambulance_id},
        )).mappings().first()

        await audit.write(
            session, actor_type="user", actor_id=str(user_row["id"]), entity="ambulances",
            entity_id=ambulance_id, action="register", before=None,
            after={"registration_no": payload.registration_no, "paramedic_phone": payload.paramedic_phone},
        )
        await session.commit()

    user = dict(user_row)
    access = _issue_tokens_for(user)
    refresh = create_refresh_token(sub=str(user["id"]), role="paramedic")
    return {
        "access_token": access, "refresh_token": refresh,
        "ambulance_id": str(ambulance_id), "kyc_verified": False,
        "user": {"id": str(user["id"]), "role": "paramedic", "name": user["name"],
                  "phone": user["phone"], "ambulance_id": str(ambulance_id)},
    }
