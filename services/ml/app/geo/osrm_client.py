"""Real OSRM client (technical.md Section9's ETA capability). Was a pure
stub (route() always returned {"code":"Ok","routes":[]}, table() always
returned empty durations/distances) -- never actually called an OSRM server.

OSRM_URL defaults to the public demo server (router.project-osrm.org),
which serves real global OSM routing data with zero setup -- good enough to
build and test real routing logic against today. technical.md Section22's
documented production path is still to self-host OSRM from a Maharashtra/
Pune OSM extract (infra/osrm/prepare_pune.sh) for the actual hackathon demo
(lower latency, no dependency on a third-party server, no rate limits) --
switching to that is purely an OSRM_URL environment variable change, no
code here changes."""

import os

import httpx

OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org")
TIMEOUT_S = 8.0


async def route(origin: dict, destination: dict, alternatives: bool = True) -> dict:
    """origin/destination: {"lat":, "lng":}. Returns the raw OSRM /route
    response (code, routes[].{distance,duration,geometry,legs})."""
    coords = f"{origin['lng']},{origin['lat']};{destination['lng']},{destination['lat']}"
    params = {"overview": "full", "geometries": "geojson", "alternatives": "true" if alternatives else "false"}
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        resp = await client.get(f"{OSRM_URL}/route/v1/driving/{coords}", params=params)
        resp.raise_for_status()
        return resp.json()


async def table(origins: list[dict], destinations: list[dict]) -> dict:
    """Returns the raw OSRM /table response (code, durations, distances)."""
    all_points = origins + destinations
    coords = ";".join(f"{p['lng']},{p['lat']}" for p in all_points)
    source_idx = ";".join(str(i) for i in range(len(origins)))
    dest_idx = ";".join(str(i) for i in range(len(origins), len(all_points)))
    params = {"sources": source_idx, "destinations": dest_idx, "annotations": "duration,distance"}
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        resp = await client.get(f"{OSRM_URL}/table/v1/driving/{coords}", params=params)
        resp.raise_for_status()
        return resp.json()
