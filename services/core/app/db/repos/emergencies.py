"""A's file (work-distribution.md §2.2). Raw parameterized SQL against the
draft schema -- see note in repos/identity.py. Every write here is one leg of
the process_emergency pipeline (technical.md §10.1); the caller
(domain/intake.py) is responsible for wrapping the whole job in one
transaction with the outbox write + audit.write, per the "one transaction =
state + audit + outbox" rule (wd-person-a-intake-dispatch.md §5)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_incident(session: AsyncSession, *, lat: float | None, lng: float | None) -> str:
    row = (await session.execute(
        text(
            "INSERT INTO incidents (location) "
            "VALUES (CASE WHEN CAST(:lat AS double precision) IS NULL THEN NULL "
            "ELSE ST_SetSRID(ST_MakePoint(CAST(:lng AS double precision), CAST(:lat AS double precision)), 4326) END) "
            "RETURNING id"
        ),
        {"lat": lat, "lng": lng},
    )).scalar_one()
    return str(row)


async def create_emergency(
    session: AsyncSession, *,
    incident_id: str,
    caller_user_id: str | None,
    caller_phone: str | None,
    channel: str,
    raw_text: str | None,
    lat: float | None,
    lng: float | None,
    accuracy_m: float | None,
    family_track_token_hash: str,
    language: str | None = None,
) -> dict:
    row = (await session.execute(
        text(
            "INSERT INTO emergencies "
            "(incident_id, caller_user_id, caller_phone, channel, raw_text, language, "
            " location, location_accuracy_m, status, family_track_token_hash, received_at) "
            "VALUES (:incident_id, :caller_user_id, :caller_phone, :channel, :raw_text, :language, "
            " CASE WHEN CAST(:lat AS double precision) IS NULL THEN NULL "
            " ELSE ST_SetSRID(ST_MakePoint(CAST(:lng AS double precision), CAST(:lat AS double precision)), 4326) END, "
            " CAST(:accuracy_m AS real), 'received', :family_track_token_hash, now()) "
            "RETURNING id, status, version"
        ),
        {
            "incident_id": incident_id, "caller_user_id": caller_user_id, "caller_phone": caller_phone,
            "channel": channel, "raw_text": raw_text, "language": language, "lat": lat, "lng": lng,
            "accuracy_m": accuracy_m, "family_track_token_hash": family_track_token_hash,
        },
    )).mappings().first()
    return dict(row)


async def create_patient_row(session: AsyncSession, *, emergency_id: str, user_id: str | None,
                              is_unknown: bool, temp_id: str | None = None) -> str:
    row = (await session.execute(
        text(
            "INSERT INTO patients (emergency_id, user_id, is_unknown, temp_id) "
            "VALUES (:emergency_id, :user_id, :is_unknown, :temp_id) RETURNING id"
        ),
        {"emergency_id": emergency_id, "user_id": user_id, "is_unknown": is_unknown, "temp_id": temp_id},
    )).scalar_one()
    return str(row)


_EMERGENCY_FULL_COLUMNS = (
    "id, status, version, caller_user_id, caller_phone, raw_text, transcript, language, "
    "stt_confidence, extracted, "
    "ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng, location_accuracy_m, "
    "location_source, landmark_text, "
    "ai_acuity, ai_facility, ai_confidence, ai_probs, needs_review, "
    "final_acuity, final_facility, "
    "required_ambulance_type, fragility, mlc_flag, prank_score, prank_verified, duplicate_of, "
    "predicted_resources, handover_note, "
    "ambulance_id, hospital_id, reservation_id, "
    "eta_to_patient_sec, eta_to_hospital_sec, eta_low_sec, eta_high_sec, escalated, "
    "received_at, triaged_at, assigned_at, at_scene_at, on_board_at, "
    "hospital_confirmed_at, arrived_hospital_at, handed_off_at, closed_at"
)
# Originally selected only a dozen of the Emergency row's ~40 real columns --
# missing ambulance_id/hospital_id/eta/timestamps meant family/patient-facing
# code had nothing non-clinical to actually show, which is what a real
# per-role privacy projection (domain/privacy.py) needs to choose from. Now
# selects every real column once (the full picture), and project() is what
# strips it down per role -- not this function silently deciding in advance.


async def get_emergency(session: AsyncSession, emergency_id: str) -> dict | None:
    row = (await session.execute(
        text(f"SELECT {_EMERGENCY_FULL_COLUMNS} FROM emergencies WHERE id = :id"),
        {"id": emergency_id},
    )).mappings().first()
    return dict(row) if row else None


async def get_emergency_by_track_token_hash(session: AsyncSession, token_hash: str) -> dict | None:
    """Family tracking (technical.md Section18/Section11): the raw token is
    handed to the client once at creation and never stored -- only its
    SHA-256 hash is, so a leaked database row can't be replayed as a token."""
    row = (await session.execute(
        text(f"SELECT {_EMERGENCY_FULL_COLUMNS} FROM emergencies WHERE family_track_token_hash = :h"),
        {"h": token_hash},
    )).mappings().first()
    return dict(row) if row else None


JSONB_COLUMNS = {"extracted", "ai_probs", "predicted_resources", "handover_note"}


async def update_emergency(session: AsyncSession, emergency_id: str, *, expected_version: int, **fields) -> dict:
    """Optimistic-locked update (technical.md §7.1): mismatch -> caller must
    surface 409 VERSION_CONFLICT with the current row. jsonb-typed columns
    (JSONB_COLUMNS) take a JSON string and are cast explicitly since this is
    raw SQL, not ORM-typed columns."""
    if not fields:
        raise ValueError("update_emergency called with no fields")

    set_clause = ", ".join(
        f"{col} = CAST(:{col} AS jsonb)" if col in JSONB_COLUMNS else f"{col} = :{col}"
        for col in fields
    )
    params = {**fields, "id": emergency_id, "expected_version": expected_version}
    row = (await session.execute(
        text(
            f"UPDATE emergencies SET {set_clause}, version = version + 1 "
            "WHERE id = :id AND version = :expected_version "
            "RETURNING id, status, version"
        ),
        params,
    )).mappings().first()
    if row is None:
        current = await get_emergency(session, emergency_id)
        raise VersionConflict(current)
    return dict(row)


class VersionConflict(Exception):
    def __init__(self, current: dict | None):
        self.current = current
        super().__init__("VERSION_CONFLICT")
