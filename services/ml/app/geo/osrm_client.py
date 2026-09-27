import httpx
import os

OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5000")

async def route(origin, destination, alternatives=True) -> dict:
    return {"code": "Ok", "routes": []}

async def table(origins: list, destinations: list) -> dict:
    return {"code": "Ok", "durations": [], "distances": []}
