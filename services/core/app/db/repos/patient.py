"""Patient self-service data: health profile, emergency contacts, own
emergency history, and the followup Q&A answer log. None of these existed
anywhere on the real backend -- /me/profile, /me/contacts, /me/emergencies,
and /emergencies/{id}/followup all 404'd, even though the real frontend
(app/patient/{profile,contacts,history}/page.tsx) already calls them."""
import json
from datetime import date
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_CONTACTS = 5


async def get_or_create_health_profile(session: AsyncSession, user_id: str) -> dict:
    row = (await session.execute(
        text("""
            SELECT u.name, hp.dob, hp.sex, hp.blood_group, hp.allergies, hp.conditions, hp.medications,
                   hp.insurance_provider, hp.insurance_policy_no, hp.home_address, hp.notes, hp.version
            FROM users u
            LEFT JOIN health_profiles hp ON hp.user_id = u.id
            WHERE u.id = :user_id
        """),
        {"user_id": user_id},
    )).mappings().first()
    if row and row["version"] is not None:
        return dict(row)
    # No health_profiles row yet (patient never saved one) -- create a bare
    # default row so the PUT below always has a real version to CAS against,
    # same reasoning as the "no silent None" rule elsewhere in this codebase.
    await session.execute(
        text("INSERT INTO health_profiles (user_id, allergies, conditions, medications, version) "
             "VALUES (:user_id, '{}', '{}', '{}', 1) ON CONFLICT (user_id) DO NOTHING"),
        {"user_id": user_id},
    )
    name = (await session.execute(text("SELECT name FROM users WHERE id = :id"), {"id": user_id})).scalar_one_or_none()
    return {
        "name": name, "dob": None, "sex": None, "blood_group": None,
        "allergies": [], "conditions": [], "medications": [],
        "insurance_provider": None, "insurance_policy_no": None,
        "home_address": None, "notes": None, "version": 1,
    }


class VersionConflict(Exception):
    pass


async def update_health_profile(
    session: AsyncSession, user_id: str, *, name: str | None, dob, sex: str | None,
    blood_group: str | None, allergies: list[str], conditions: list[str], medications: list[str],
    home_address: str | None, notes: str | None, expected_version: int,
) -> dict:
    if name is not None:
        await session.execute(text("UPDATE users SET name = :name WHERE id = :id"), {"name": name, "id": user_id})

    # asyncpg needs a real datetime.date object for a date-typed parameter --
    # a CAST(:dob AS date) in the SQL doesn't help, since asyncpg binds the
    # parameter by its inferred prepared-statement type before Postgres ever
    # sees the CAST. An ISO "YYYY-MM-DD" string from the frontend's <input
    # type="date"> raised "'str' object has no attribute 'toordinal'" the
    # first time this was actually called with a real date.
    dob_value = date.fromisoformat(dob) if isinstance(dob, str) and dob else None

    # UPSERT, not a plain UPDATE: the real frontend always GETs first (which
    # creates the default row), but PUT shouldn't silently depend on that
    # call order -- a bare UPDATE against a not-yet-existing row matches
    # zero rows for exactly the same reason a real version mismatch would,
    # so the two cases were indistinguishable and a first-ever save with no
    # prior GET always 409'd. ON CONFLICT only applies the version check
    # (version = :expected_version) on the UPDATE branch; the INSERT branch
    # only runs when no row exists yet, where there's nothing to conflict with.
    row = (await session.execute(
        text("""
            INSERT INTO health_profiles (user_id, dob, sex, blood_group, allergies, conditions, medications,
                                          home_address, notes, version)
            VALUES (:user_id, :dob, :sex, :blood_group, :allergies, :conditions, :medications,
                    :home_address, :notes, 1)
            ON CONFLICT (user_id) DO UPDATE SET
                dob = :dob, sex = :sex, blood_group = :blood_group,
                allergies = :allergies, conditions = :conditions, medications = :medications,
                home_address = :home_address, notes = :notes, version = health_profiles.version + 1
            WHERE health_profiles.version = :expected_version
            RETURNING dob, sex, blood_group, allergies, conditions, medications,
                      insurance_provider, insurance_policy_no, home_address, notes, version
        """),
        {
            "user_id": user_id, "dob": dob_value, "sex": sex, "blood_group": blood_group,
            "allergies": allergies, "conditions": conditions, "medications": medications,
            "home_address": home_address, "notes": notes, "expected_version": expected_version,
        },
    )).mappings().first()
    if row is None:
        raise VersionConflict()
    result = dict(row)
    result["name"] = name
    return result


async def list_emergency_contacts(session: AsyncSession, user_id: str) -> list[dict]:
    rows = (await session.execute(
        text("SELECT id, name, phone, relation, language, priority FROM emergency_contacts "
             "WHERE user_id = :user_id ORDER BY priority NULLS LAST, created_at ASC"),
        {"user_id": user_id},
    )).mappings().all()
    return [dict(r) for r in rows]


class TooManyContacts(Exception):
    pass


async def create_emergency_contact(
    session: AsyncSession, user_id: str, *, name: str, phone: str, relation: str | None, language: str | None,
) -> dict:
    count = (await session.execute(
        text("SELECT count(*) FROM emergency_contacts WHERE user_id = :user_id"), {"user_id": user_id}
    )).scalar_one()
    if count >= MAX_CONTACTS:
        raise TooManyContacts()
    row = (await session.execute(
        text("INSERT INTO emergency_contacts (user_id, name, phone, relation, language, priority) "
             "VALUES (:user_id, :name, :phone, :relation, :language, :priority) "
             "RETURNING id, name, phone, relation, language, priority"),
        {"user_id": user_id, "name": name, "phone": phone, "relation": relation,
         "language": language, "priority": count + 1},
    )).mappings().first()
    return dict(row)


async def delete_emergency_contact(session: AsyncSession, user_id: str, contact_id: str) -> bool:
    result = await session.execute(
        text("DELETE FROM emergency_contacts WHERE id = :id AND user_id = :user_id"),
        {"id": contact_id, "user_id": user_id},
    )
    return result.rowcount > 0


async def list_my_emergencies(session: AsyncSession, user_id: str, *, limit: int = 50) -> list[dict]:
    rows = (await session.execute(
        text("""
            SELECT em.id, em.status, em.final_acuity, em.ai_acuity, em.final_facility, em.ai_facility,
                   em.received_at, h.name AS hospital_name,
                   -- for_self: the intake pipeline today always creates the
                   -- patient row under the caller's own user_id (no "report
                   -- for someone else with a known identity" path exists
                   -- yet, confirmed: create_patient_row is only ever called
                   -- with user_id=caller_user_id) -- so this is accurate,
                   -- not a placeholder, given what intake actually captures.
                   (p.user_id IS NOT NULL AND p.user_id = em.caller_user_id) AS for_self
            FROM emergencies em
            LEFT JOIN hospitals h ON h.id = em.hospital_id
            LEFT JOIN patients p ON p.emergency_id = em.id
            WHERE em.caller_user_id = :user_id
            ORDER BY em.received_at DESC LIMIT :limit
        """),
        {"user_id": user_id, "limit": limit},
    )).mappings().all()
    return [dict(r) for r in rows]


async def list_followup_answers(session: AsyncSession, emergency_id: str) -> list[dict]:
    rows = (await session.execute(
        text("SELECT question_id, answer_raw, answer_parsed FROM followup_answers "
             "WHERE emergency_id = :id ORDER BY created_at ASC"),
        {"id": emergency_id},
    )).mappings().all()
    return [dict(r) for r in rows]


async def record_followup_answer(
    session: AsyncSession, emergency_id: str, *, question_id: str, answer_raw: str,
    answer_parsed, language: str,
) -> None:
    await session.execute(
        text("INSERT INTO followup_answers (emergency_id, question_id, answer_raw, answer_parsed, language) "
             "VALUES (:emergency_id, :question_id, :answer_raw, CAST(:answer_parsed AS jsonb), :language)"),
        {"emergency_id": emergency_id, "question_id": question_id, "answer_raw": answer_raw,
         "answer_parsed": json.dumps(answer_parsed), "language": language},
    )
