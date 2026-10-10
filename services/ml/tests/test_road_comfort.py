"""Real road comfort (technical.md Section9.12). Was mock-only: a constant
score=75.0 with all-zero components for every request, regardless of
input. Now scores the real OSM road segments a route's geometry passes
through (app/geo/edges_store.py) plus the route's own curvature."""

import asyncio

from app.capabilities.eta.model import get_eta
from app.capabilities.eta.schemas import ETARequest, Point
from app.capabilities.road_comfort.model import real_road_comfort
from app.capabilities.road_comfort.schemas import RoadComfortRequest


def _comfort_for_route(origin: Point, dest: Point):
    async def _run():
        eta_resp = await get_eta(ETARequest(origin=origin, destination=dest))
        return await real_road_comfort(RoadComfortRequest(geometry=eta_resp.routes[0].geometry))
    return asyncio.run(_run())


def test_real_route_gets_non_constant_score():
    result = _comfort_for_route(Point(lat=18.5196, lng=73.8553), Point(lat=18.5118, lng=73.8520))
    assert result.estimated is False
    assert result.data_coverage == 1.0
    # the old mock always returned exactly 75.0 with all-zero components
    assert not (result.score == 75.0 and result.components.surface == 0)


def test_two_different_routes_score_differently():
    short_route = _comfort_for_route(Point(lat=18.5196, lng=73.8553), Point(lat=18.5118, lng=73.8520))
    long_route = _comfort_for_route(Point(lat=18.5618, lng=73.8101), Point(lat=18.4536, lng=73.8563))
    assert short_route.score != long_route.score
    assert short_route.components.class_val != long_route.components.class_val


def test_empty_geometry_falls_back_to_mock():
    result = asyncio.run(real_road_comfort(RoadComfortRequest(geometry="")))
    assert result.estimated is True
