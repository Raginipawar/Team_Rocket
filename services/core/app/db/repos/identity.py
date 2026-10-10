"""A's file (work-distribution.md §2.2). Raw parameterized SQL against the
draft schema (db/migrations/0001_init.sql) rather than ORM models, so this
doesn't fight with whatever ORM models B eventually defines over the same
tables -- swap the query bodies for ORM calls later without changing the
function signatures repos/emergencies.py and domain/intake.py depend on."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_by_phone(session: AsyncSession, phone: str) -> dict | None:
    """Phone-only lookup -- ambiguous if the same phone has rows under more
    than one role (demo need: only 2 real phones, same number used for both
    a patient and an ambulance account). Fine for callers that only ever
    deal with one role's accounts; get_user_by_phone_and_role is the real
    role-aware lookup used by OTP login."""
    row = (await session.execute(
        text("SELECT id, role, name, phone, language FROM users WHERE phone = :phone"),
        {"phone": phone},
    )).mappings().first()
    return dict(row) if row else None


async def get_user_by_phone_and_role(session: AsyncSession, phone: str, role: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, role, name, phone, language, ambulance_id FROM users WHERE phone = :phone AND role = :role"),
        {"phone": phone, "role": role},
    )).mappings().first()
    return dict(row) if row else None


async def create_patient_user(session: AsyncSession, phone: str, *, name: str | None = None,
                               language: str = "en") -> dict:
    row = (await session.execute(
        text(
            "INSERT INTO users (role, name, phone, language) "
            "VALUES ('patient', :name, :phone, :language) "
            "RETURNING id, role, name, phone, language"
        ),
        {"name": name, "phone": phone, "language": language},
    )).mappings().first()
    return dict(row)


async def get_or_create_patient_user(session: AsyncSession, phone: str, *, language: str = "en") -> dict:
    existing = await get_user_by_phone_and_role(session, phone, "patient")
    if existing:
        return existing
    return await create_patient_user(session, phone, language=language)


async def get_or_create_paramedic_user(session: AsyncSession, phone: str, *, language: str = "en") -> dict:
    """Ambulance app OTP login (replaces the fixed phone+password demo
    login). A phone-verified paramedic with no ambulance_id yet is a real,
    valid state -- they haven't registered/selected an ambulance (Live) or
    generated a demo one (Demo) yet. Returns ambulance_id/registration_status
    so the frontend can route to the right step.

    Looked up by (phone, role), not phone alone -- the same phone can have
    a patient row AND a paramedic row (demo need: only 2 real phones to
    test with), each its own account, not a role conflict."""
    row = await get_user_by_phone_and_role(session, phone, "paramedic")
    if row:
        user = dict(row)
    else:
        user = dict((await session.execute(
            text("INSERT INTO users (role, name, phone, language) VALUES ('paramedic', NULL, :phone, :language) "
                 "RETURNING id, role, name, phone, language, ambulance_id"),
            {"phone": phone, "language": language},
        )).mappings().first())
    if user.get("ambulance_id"):
        amb = (await session.execute(
            text("SELECT registration_status FROM ambulances WHERE id = :id"), {"id": user["ambulance_id"]},
        )).mappings().first()
        user["registration_status"] = amb["registration_status"] if amb else None
    else:
        user["registration_status"] = None
    return user


async def store_otp(session: AsyncSession, phone: str, code_hash: str, expires_at) -> None:
    await session.execute(
        text("DELETE FROM otp_codes WHERE phone = :phone"),
        {"phone": phone},
    )
    await session.execute(
        text("INSERT INTO otp_codes (phone, code_hash, expires_at, attempts) VALUES (:phone, :code_hash, :expires_at, 0)"),
        {"phone": phone, "code_hash": code_hash, "expires_at": expires_at},
    )


async def get_otp(session: AsyncSession, phone: str) -> dict | None:
    row = (await session.execute(
        text("SELECT phone, code_hash, expires_at, attempts FROM otp_codes WHERE phone = :phone"),
        {"phone": phone},
    )).mappings().first()
    return dict(row) if row else None


async def increment_otp_attempts(session: AsyncSession, phone: str) -> int:
    row = (await session.execute(
        text("UPDATE otp_codes SET attempts = attempts + 1 WHERE phone = :phone RETURNING attempts"),
        {"phone": phone},
    )).scalar_one_or_none()
    return row or 0


async def delete_otp(session: AsyncSession, phone: str) -> None:
    await session.execute(text("DELETE FROM otp_codes WHERE phone = :phone"), {"phone": phone})


async def get_user_by_username_or_phone(session: AsyncSession, identifier: str) -> dict | None:
    row = (await session.execute(
        text(
            "SELECT id, role, name, phone, language, password_hash, hospital_id, ambulance_id "
            "FROM users WHERE phone = :id OR name = :id"
        ),
        {"id": identifier},
    )).mappings().first()
    return dict(row) if row else None


async def get_user_by_id(session: AsyncSession, user_id: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, role, name, phone, language, hospital_id, ambulance_id, is_active FROM users WHERE id = :id"),
        {"id": user_id},
    )).mappings().first()
    return dict(row) if row else None


async def get_user_ids_by_ambulance_id(session: AsyncSession, ambulance_id: str) -> list[str]:
    """The paramedic(s) logged in as a given ambulance -- used to push a new
    offer to the right person (technical.md Section12.3). No caller existed
    for this lookup before; push notifications had no way to find who to
    notify."""
    rows = (await session.execute(
        text("SELECT id FROM users WHERE ambulance_id = :aid AND is_active"),
        {"aid": ambulance_id},
    )).scalars().all()
    return [str(r) for r in rows]


async def get_user_ids_by_hospital_id(session: AsyncSession, hospital_id: str) -> list[str]:
    """All hospital_staff users at a hospital -- a new hospital request
    pushes to everyone on duty there, not one specific person."""
    rows = (await session.execute(
        text("SELECT id FROM users WHERE hospital_id = :hid AND role = 'hospital_staff' AND is_active"),
        {"hid": hospital_id},
    )).scalars().all()
    return [str(r) for r in rows]


async def create_staff_user(session: AsyncSession, *, role: str, name: str, phone: str | None,
                             password_hash: str, hospital_id: str | None = None,
                             ambulance_id: str | None = None) -> dict:
    row = (await session.execute(
        text(
            "INSERT INTO users (role, name, phone, password_hash, hospital_id, ambulance_id) "
            "VALUES (:role, :name, :phone, :password_hash, :hospital_id, :ambulance_id) "
            "RETURNING id, role, name, phone, hospital_id, ambulance_id"
        ),
        {"role": role, "name": name, "phone": phone, "password_hash": password_hash,
         "hospital_id": hospital_id, "ambulance_id": ambulance_id},
    )).mappings().first()
    return dict(row)


async def get_health_profile(session: AsyncSession, user_id: str) -> dict | None:
    row = (await session.execute(
        text(
            "SELECT user_id, dob, sex, blood_group, allergies, conditions, medications, "
            "ST_Y(home_location::geometry) AS home_lat, ST_X(home_location::geometry) AS home_lng "
            "FROM health_profiles WHERE user_id = :user_id"
        ),
        {"user_id": user_id},
    )).mappings().first()
    return dict(row) if row else None
