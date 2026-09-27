"""A's file (work-distribution.md §2.2). Raw parameterized SQL against the
draft schema (db/migrations/0001_init.sql) rather than ORM models, so this
doesn't fight with whatever ORM models B eventually defines over the same
tables -- swap the query bodies for ORM calls later without changing the
function signatures repos/emergencies.py and domain/intake.py depend on."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_by_phone(session: AsyncSession, phone: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, role, name, phone, language FROM users WHERE phone = :phone"),
        {"phone": phone},
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
    existing = await get_user_by_phone(session, phone)
    if existing:
        return existing
    return await create_patient_user(session, phone, language=language)


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
