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


async def get_patient_route_view(session: AsyncSession, ambulance_id: str, emergency: dict) -> dict:
    """EmergencyView.route/leg (api-types.ts) -- GET /emergencies/{id} never
    populated either, full stop, regardless of GPS state: the patient's own
    map had no route line for any emergency, ever. Mirrors the exact leg/
    route_target logic GET /ambulance/active already uses (api/v1/ambulance.py)
    so both sides agree on which leg is "current" and compute the same route."""
    from app.integrations.ml.routing import get_route

    leg = "to_hospital" if emergency.get("status") in (
        "on_board", "hospital_selecting", "hospital_confirmed", "arrived_hospital",
    ) else "to_patient"

    amb_loc = (await session.execute(
        text("SELECT ST_Y(current_location::geometry) AS lat, ST_X(current_location::geometry) AS lng "
             "FROM ambulances WHERE id = :id"), {"id": ambulance_id},
    )).mappings().first()

    route_target = None
    if leg == "to_patient" and emergency.get("lat") is not None:
        route_target = {"lat": emergency["lat"], "lng": emergency["lng"]}
    elif leg == "to_hospital" and emergency.get("hospital_id"):
        hosp = (await session.execute(
            text("SELECT ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng "
                 "FROM hospitals WHERE id = :id"), {"id": emergency["hospital_id"]},
        )).mappings().first()
        if hosp:
            route_target = {"lat": hosp["lat"], "lng": hosp["lng"]}

    route = None
    if amb_loc and amb_loc["lat"] is not None and route_target:
        route_data = await get_route(None, {"lat": amb_loc["lat"], "lng": amb_loc["lng"]}, route_target)
        route = route_data.get("geometry") if route_data else None
    return {"route": route, "leg": leg}
