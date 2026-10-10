"""Real OSRM-backed ETA (technical.md Section9). Was a pure pass-through to
the haversine mock (osrm_client.py's route()/table() always returned empty
stubs) -- now calls the real OSRM API, with the mock as a genuine fallback
only, verified by actually breaking the connection."""

import asyncio

import pytest

from app.capabilities.eta.model import get_eta, get_eta_matrix
from app.capabilities.eta.schemas import ETAMatrixRequest, ETARequest, Point

# Pune coordinates, real route expected to exist
ORIGIN = Point(lat=18.5196, lng=73.8553)
DEST = Point(lat=18.5118, lng=73.8520)


def test_real_eta_returns_osrm_route():
    req = ETARequest(origin=ORIGIN, destination=DEST)
    resp = asyncio.run(get_eta(req))
    assert len(resp.routes) >= 1
    route = resp.routes[0]
    assert route.source == "osrm"
    assert route.distance_m > 0
    assert route.eta_sec > 0
    assert route.eta_low_sec < route.eta_sec < route.eta_high_sec


def test_real_eta_matrix_returns_osrm_data():
    req = ETAMatrixRequest(origins=[ORIGIN], destinations=[DEST])
    resp = asyncio.run(get_eta_matrix(req))
    assert resp.durations[0][0] > 0
    assert resp.distances[0][0] > 0


def test_eta_falls_back_to_haversine_when_osrm_unreachable(monkeypatch):
    import app.capabilities.eta.model as eta_model

    async def _broken_route(*args, **kwargs):
        raise ConnectionError("simulated OSRM outage")

    monkeypatch.setattr(eta_model.osrm_client, "route", _broken_route)
    req = ETARequest(origin=ORIGIN, destination=DEST)
    resp = asyncio.run(get_eta(req))
    assert resp.routes[0].source == "mock_haversine"
