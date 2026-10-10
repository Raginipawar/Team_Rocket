"""Real ETA: calls OSRM (app/geo/osrm_client.py) for actual road routing.
Was a pure pass-through to the haversine mock -- never called OSRM at all.
Mock is now only the documented fallback if OSRM is unreachable, not the
default path."""

import logging
import uuid

from app.geo import osrm_client

from .mock import get_eta_matrix_mock, get_eta_mock
from .schemas import ETAMatrixRequest, ETAMatrixResponse, ETARequest, ETAResponse, Route, Step

logger = logging.getLogger("eta")

# OSRM gives a point duration estimate with no uncertainty band of its own;
# +-15% is a documented, simple band (not a statistically fit one) until a
# real historical-traffic-variance model exists.
UNCERTAINTY_PCT = 0.15


async def get_eta(req: ETARequest) -> ETAResponse:
    origin = {"lat": req.origin.lat, "lng": req.origin.lng}
    destination = {"lat": req.destination.lat, "lng": req.destination.lng}
    try:
        data = await osrm_client.route(origin, destination, alternatives=req.alternatives)
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM returned no route: {data.get('code')}")

        routes = []
        for r in data["routes"]:
            eta_sec = r["duration"]
            routes.append(Route(
                route_id=str(uuid.uuid4()),
                # OSRM's own polyline6 output -- matches the frontend's
                # decodePolyline6 (standard Google polyline algorithm,
                # precision 1e6) exactly, so no custom re-encoding needed.
                # The previous geojson-based _encode_geometry() produced a
                # completely different "lng,lat;lng,lat" string that
                # decodePolyline6 would have silently mis-parsed.
                geometry=r.get("geometry", ""),
                distance_m=r["distance"],
                eta_sec=eta_sec,
                eta_low_sec=eta_sec * (1 - UNCERTAINTY_PCT),
                eta_high_sec=eta_sec * (1 + UNCERTAINTY_PCT),
                source="osrm",
                steps=_extract_steps(r.get("legs", [])),
            ))
        return ETAResponse(routes=routes)
    except Exception:
        logger.exception("OSRM route call failed -- falling back to haversine estimate")
        return await get_eta_mock(req)


async def get_eta_matrix(req: ETAMatrixRequest) -> ETAMatrixResponse:
    origins = [{"lat": p.lat, "lng": p.lng} for p in req.origins]
    destinations = [{"lat": p.lat, "lng": p.lng} for p in req.destinations]
    try:
        data = await osrm_client.table(origins, destinations)
        if data.get("code") != "Ok":
            raise ValueError(f"OSRM returned: {data.get('code')}")
        return ETAMatrixResponse(durations=data["durations"], distances=data["distances"])
    except Exception:
        logger.exception("OSRM table call failed -- falling back to haversine estimate")
        return await get_eta_matrix_mock(req)


_MODIFIER_TEXT = {
    "uturn": "Make a U-turn", "sharp right": "Turn sharp right", "right": "Turn right",
    "slight right": "Turn slightly right", "straight": "Continue straight",
    "slight left": "Turn slightly left", "left": "Turn left", "sharp left": "Turn sharp left",
}


def _step_instruction(maneuver: dict, road_name: str | None) -> str:
    # OSRM's real maneuver.type/modifier (technical.md's own turn-by-turn
    # requirement) -- not a made-up string. Was previously nothing at all:
    # the core API's /ambulance/active response hardcoded turns=None, so the
    # frontend's whole turn-by-turn UI had nothing real to ever show.
    mtype = maneuver.get("type", "turn")
    modifier = maneuver.get("modifier")
    suffix = f" onto {road_name}" if road_name else ""
    if mtype == "depart":
        return f"Head out{suffix}" if road_name else "Head out"
    if mtype == "arrive":
        return "You have arrived"
    if mtype in ("turn", "end of road", "fork", "merge", "on ramp", "off ramp", "new name"):
        base = _MODIFIER_TEXT.get(modifier or "straight", "Continue")
        return f"{base}{suffix}"
    if mtype in ("roundabout", "rotary", "roundabout turn", "exit roundabout", "exit rotary"):
        return f"Take the roundabout{suffix}"
    return f"Continue{suffix}"


def _extract_steps(legs: list[dict]) -> list[Step]:
    steps: list[Step] = []
    for leg in legs:
        for s in leg.get("steps", []):
            maneuver = s.get("maneuver", {})
            steps.append(Step(
                instruction=_step_instruction(maneuver, s.get("name") or None),
                distance_m=s.get("distance", 0.0),
                maneuver_type=maneuver.get("type", "turn"),
                maneuver_modifier=maneuver.get("modifier"),
            ))
    return steps


