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
