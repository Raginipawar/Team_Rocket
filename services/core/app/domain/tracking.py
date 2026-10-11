"""Builds the `ambulance` tracking view the patient/family live-emergency
screen expects (apps/web/lib/api-types.ts AmbulanceView) -- GET /emergencies/
{id} only ever returned flat ambulance_id/eta_to_patient_sec/... columns,
never this nested shape, and no WS event ever populated the frontend's
`live` state either (grep for "ambulance.location" emit found zero call
sites). The whole ambulance-tracking card -- ETA, map dot, heading -- was
silently dead for every real emergency; nothing ever threw, so nothing
showed up as an error, it just never rendered (`const amb = e.ambulance`
was always undefined)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

HEARTBEAT_FRESH_SEC = 30
HEARTBEAT_WEAK_SEC = 90


def signal_from_heartbeat_age(age_sec: float | None) -> str:
    if age_sec is None:
        return "lost"
    if age_sec <= HEARTBEAT_FRESH_SEC:
        return "ok"
    if age_sec <= HEARTBEAT_WEAK_SEC:
        return "weak"
    return "lost"


def pick_eta(emergency: dict) -> tuple[int | None, int | None, int | None]:
    # Before pickup, "arriving" means arriving at the patient; after pickup,
    # it means arriving at the hospital -- the two columns this row already
    # carries (emergencies_repo._EMERGENCY_FULL_COLUMNS), just never surfaced.
    if emergency.get("status") in ("patient_on_board", "at_scene") or emergency.get("on_board_at"):
        return emergency.get("eta_to_hospital_sec"), emergency.get("eta_low_sec"), emergency.get("eta_high_sec")
    return emergency.get("eta_to_patient_sec"), emergency.get("eta_low_sec"), emergency.get("eta_high_sec")


async def get_ambulance_view(session: AsyncSession, ambulance_id: str, emergency: dict) -> dict | None:
    row = (await session.execute(
        text("""
            SELECT registration_no, type, is_simulated, heading,
                   ST_Y(current_location::geometry) AS lat, ST_X(current_location::geometry) AS lng,
                   EXTRACT(EPOCH FROM (now() - last_heartbeat_at)) AS heartbeat_age_sec
            FROM ambulances WHERE id = :id
        """),
        {"id": ambulance_id},
    )).mappings().first()
    if row is None:
        return None
    eta_sec, eta_low_sec, eta_high_sec = pick_eta(emergency)
    return {
        "registration_no": row["registration_no"],
        "type": row["type"],
        "location": {"lat": row["lat"], "lng": row["lng"]} if row["lat"] is not None else None,
        "heading": row["heading"],
        "eta_sec": eta_sec, "eta_low_sec": eta_low_sec, "eta_high_sec": eta_high_sec,
        "signal": signal_from_heartbeat_age(row["heartbeat_age_sec"]),
        "is_simulated": row["is_simulated"],
    }
