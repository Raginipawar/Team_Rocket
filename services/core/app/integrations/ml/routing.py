import asyncio

async def get_eta(ml_client, origin, destination, depart_at) -> dict:
    # mock ML client call
    await asyncio.sleep(0.1)
    return {"minutes": 15, "seconds": 900}

async def get_eta_matrix(ml_client, origins, destinations) -> dict:
    return {}

async def get_road_comfort(ml_client, geometry: str) -> dict:
    return {"score": 0.8}

async def hospital_rank(ml_client, emergency: dict, candidates: list[dict]) -> list[dict]:
    # Technical.md §9: 2s timeout
    try:
        async with asyncio.timeout(2.0):
            # mock call
            await asyncio.sleep(0.1)
            # return sorted by some metric
            return sorted(candidates, key=lambda x: x.get("eta", 999))
    except asyncio.TimeoutError:
        # Fallback: utility sort
        return sorted(candidates, key=lambda x: x.get("eta", 999))

async def bed_nowcast(ml_client, hospital_id, room_type, last_reported_free, minutes_since_report, eta_min) -> dict:
    try:
        async with asyncio.timeout(2.0):
            await asyncio.sleep(0.1)
            return {"score": 0.9, "predicted_free": last_reported_free}
    except asyncio.TimeoutError:
        return {"score": 0.5, "predicted_free": last_reported_free}

async def mci_allocate(ml_client, patients, hospitals, ambulances) -> dict:
    try:
        async with asyncio.timeout(10.0):
            await asyncio.sleep(0.5)
            return {"allocations": []}
    except asyncio.TimeoutError:
        return {"allocations": []}
