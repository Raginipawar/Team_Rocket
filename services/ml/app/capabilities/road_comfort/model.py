"""Real road comfort (technical.md Section9.12): scores a route's geometry
by the real OSM attributes (surface, highway class, traffic calming) of the
road segments it actually passes through, plus the route's own curvature
(sharp turns reduce comfort for a fragile patient, independent of road
quality). Was mock-only (a constant 75.0/0 components for every request) --
app/geo/edges_store.py existed but was never called by anything."""

import logging
import math

from app.geo.edges_store import EdgesStore

from .schemas import RoadComfortComponents, RoadComfortRequest, RoadComfortResponse

logger = logging.getLogger("road_comfort")

_store = EdgesStore()

SAMPLE_STRIDE = 3  # sample every Nth point on long geometries -- comfort doesn't need every vertex
SHARP_TURN_DEG = 45.0  # a heading change sharper than this counts as a "turn" for the turns component


def _parse_geometry(geometry: str) -> list[tuple[float, float]]:
    """Matches eta/model.py's _encode_geometry: "lng,lat;lng,lat;...". Returns [(lat, lng), ...]."""
    points = []
    for pair in geometry.split(";"):
        if not pair:
            continue
        lng_str, lat_str = pair.split(",")
        points.append((float(lat_str), float(lng_str)))
    return points


def _bearing(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    lat1, lng1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lng2 = math.radians(p2[0]), math.radians(p2[1])
    dlng = lng2 - lng1
    y = math.sin(dlng) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlng)
    return math.degrees(math.atan2(y, x)) % 360


def _turns_score(points: list[tuple[float, float]]) -> float:
    """Fraction of consecutive segments WITHOUT a sharp heading change --
    1.0 = a straight route, lower = more sharp turns (less comfortable for
    a fragile/critical patient)."""
    if len(points) < 3:
        return 1.0
    sharp = 0
    total = 0
    prev_bearing = _bearing(points[0], points[1])
    for i in range(1, len(points) - 1):
        b = _bearing(points[i], points[i + 1])
        delta = abs((b - prev_bearing + 180) % 360 - 180)
        total += 1
        if delta > SHARP_TURN_DEG:
            sharp += 1
        prev_bearing = b
    return 1.0 - (sharp / total if total else 0.0)


async def real_road_comfort(req: RoadComfortRequest) -> RoadComfortResponse:
    points = _parse_geometry(req.geometry)
    if not points:
        from .mock import get_road_comfort_mock
        return await get_road_comfort_mock(req)

    sampled = points[::SAMPLE_STRIDE] or points
    try:
        edge_scores = _store.get_comfort_for_points(sampled)
    except Exception:
        logger.exception("edges_store lookup failed -- falling back to mock")
        from .mock import get_road_comfort_mock
        return await get_road_comfort_mock(req)

    n = len(edge_scores)
    surface = sum(e["surface"] for e in edge_scores) / n
    smoothness = sum(e["smoothness"] for e in edge_scores) / n
    class_val = sum(e["class_val"] for e in edge_scores) / n
    breakers = sum(e["breakers"] for e in edge_scores) / n
    turns = _turns_score(points)

    score = 100 * (0.3 * surface + 0.25 * smoothness + 0.2 * class_val + 0.1 * breakers + 0.15 * turns)

    return RoadComfortResponse(
        score=round(score, 1),
        components=RoadComfortComponents(
            surface=round(surface, 3), smoothness=round(smoothness, 3),
            class_val=round(class_val, 3), breakers=round(breakers, 3), turns=round(turns, 3),
        ),
        data_coverage=1.0,
        estimated=False,
    )
