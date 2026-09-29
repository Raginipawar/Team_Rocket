import httpx
import os

MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", "")

async def directions_traffic(origin, destination) -> dict | None:
    try:
        return {"code": "Ok", "routes": []}
    except Exception:
        return None
