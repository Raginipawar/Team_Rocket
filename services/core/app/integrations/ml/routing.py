"""Real HTTP calls to services/ml (technical.md §9.11-9.14, §9.17).

The previous version of this file was entirely hardcoded dict literals
(`return {"minutes": 15, "seconds": 900}` no matter what was asked) --
nothing in it ever actually called the ML service, despite being the one
place core is supposed to reach it for ETA/road-comfort/hospital-rank/bed-
nowcast/MCI. This version makes real HTTP calls, with the exact fallback
behaviour technical.md documents for each capability if the call fails --
fallback is a resilience path, not a substitute for the real call always
being attempted first."""

import math
import os

import httpx

ML_BASE_URL = os.getenv("ML_BASE_URL", "http://localhost:8001")
ASSUMED_SPEED_KMH = 30.0


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def get_eta(ml_client, origin: dict, destination: dict, depart_at) -> dict:
    """technical.md §9.11. origin/destination are {"lat":.., "lng":..} dicts.
    Fallback: haversine distance / assumed speed -- always a number, never silence."""
    try:
        async with httpx.AsyncClient(base_url=ML_BASE_URL, timeout=3.0) as client:
            resp = await client.post("/ml/v1/eta", json={"origin": origin, "destination": destination})
            resp.raise_for_status()
            route = resp.json()["routes"][0]  # schemas.py: ETAResponse.routes[0], not a flat field
            return {"minutes": route["eta_sec"] / 60, "seconds": route["eta_sec"]}
    except (httpx.HTTPError, KeyError, IndexError):
        dist_km = _haversine_km(origin["lat"], origin["lng"], destination["lat"], destination["lng"])
        seconds = max(30, round((dist_km / ASSUMED_SPEED_KMH) * 3600))
        return {"minutes": seconds / 60, "seconds": seconds}


async def get_eta_matrix(ml_client, origins: list[dict], destinations: list[dict]) -> dict:
    try:
        async with httpx.AsyncClient(base_url=ML_BASE_URL, timeout=5.0) as client:
            resp = await client.post("/ml/v1/eta/matrix", json={"origins": origins, "destinations": destinations})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError:
        return {
            "matrix": [
                [await get_eta(None, o, d, None) for d in destinations]
                for o in origins
            ]
        }


async def get_road_comfort(ml_client, geometry: str) -> dict:
    try:
        async with httpx.AsyncClient(base_url=ML_BASE_URL, timeout=2.0) as client:
            resp = await client.post("/ml/v1/road-comfort", json={"geometry": geometry})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError:
        return {"score": 0.5}  # neutral fallback, not a confident guess


async def hospital_rank(ml_client, emergency: dict, candidates: list[dict]) -> list[dict]:
    """technical.md §9.13: 2s timeout. On failure, core sorts eligible
    candidates by the utility function directly (same formula the ML
    service's own mock uses, so the fallback and the real model agree on
    what 'good' means)."""
    try:
        async with httpx.AsyncClient(base_url=ML_BASE_URL, timeout=2.0) as client:
            resp = await client.post("/ml/v1/hospital-rank", json={"emergency": emergency, "candidates": candidates})
            resp.raise_for_status()
            return resp.json()  # services/ml/app/capabilities/hospital_rank: response_model=list[...], a bare list
    except httpx.HTTPError:
        ranked = []
        for c in candidates:
            f = c.get("features", c)
            eta_sec = f.get("eta_sec", f.get("eta", 999) * 60)
            p_no_bed = 1 - f.get("p_bed_available_at_eta", 0.5)
            p_no_specialist = 0 if f.get("specialist_on_duty_at_eta", f.get("specialist", True)) else 1
            utility = eta_sec + p_no_bed * 900 + p_no_specialist * 300
            if emergency.get("fragility"):
                utility -= f.get("road_comfort", f.get("road_comfort_score", 0.5)) * 120
            eligible = f.get("is_active", True) and (f.get("facility_match", 1) or f.get("stabilization_capable"))
            ranked.append({**c, "score": -utility if eligible else -1e9, "eligible": bool(eligible)})
        ranked.sort(key=lambda r: r["score"], reverse=True)
        for i, r in enumerate(ranked):
            r["rank"] = i + 1
        return ranked


async def bed_nowcast(ml_client, hospital_id, room_type, last_reported_free, minutes_since_report, eta_min) -> dict:
    try:
        async with httpx.AsyncClient(base_url=ML_BASE_URL, timeout=2.0) as client:
            resp = await client.post("/ml/v1/bed-nowcast", json={
                "hospital_id": str(hospital_id), "room_type": room_type,
                "last_reported_free": last_reported_free, "minutes_since_report": minutes_since_report,
                "eta_min": eta_min,
            })
            resp.raise_for_status()
            data = resp.json()
            return {"score": data.get("p_available_at_eta", 0.5), "predicted_free": data.get("expected_free_at_eta", last_reported_free)}
    except httpx.HTTPError:
        return {"score": 0.5, "predicted_free": last_reported_free}


async def mci_allocate(ml_client, patients, hospitals, ambulances) -> dict:
    """patients: [{"id","acuity","facility"}], hospitals: [{"id",
    "capacities_by_type","eta_sec"}], ambulances: [{"id","type",
    "eta_to_scene"}] -- services/ml/app/capabilities/mci/schemas.py's exact
    field names. The fallback below used to return {"allocations": []},
    which doesn't match the real success shape
    ({"assignments","unassigned","objective"}) at all -- any caller that
    checked result["assignments"] after a ML-service outage would have
    gotten a KeyError instead of the intended empty-but-well-shaped fallback."""
    try:
        async with httpx.AsyncClient(base_url=ML_BASE_URL, timeout=10.0) as client:
            resp = await client.post("/ml/v1/mci-allocate", json={
                "patients": patients, "hospitals": hospitals, "ambulances": ambulances,
            })
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError:
        return {
            "assignments": [],
            "unassigned": [{"patient_id": p["id"], "reason": "ml_service_unavailable"} for p in patients],
            "objective": 0.0,
        }
