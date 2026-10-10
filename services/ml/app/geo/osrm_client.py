import httpx
import os

OSRM_URL = os.environ.get("OSRM_URL", "http://osrm:5000")

async def route(origin, destination, alternatives=True) -> dict:
    url = f"{OSRM_URL}/route/v1/driving/{origin.lng},{origin.lat};{destination.lng},{destination.lat}"
    params = {
        "alternatives": "true" if alternatives else "false",
        "overview": "full",
        "steps": "false",
        "annotations": "false"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"code": "Error", "routes": [], "message": str(e)}

async def table(origins: list, destinations: list) -> dict:
    coords = []
    sources = []
    dests = []
    
    idx = 0
    for o in origins:
        coords.append(f"{o.lng},{o.lat}")
        sources.append(str(idx))
        idx += 1
        
    for d in destinations:
        coords.append(f"{d.lng},{d.lat}")
        dests.append(str(idx))
        idx += 1
        
    coord_str = ";".join(coords)
    sources_str = ";".join(sources)
    dests_str = ";".join(dests)
    
    url = f"{OSRM_URL}/table/v1/driving/{coord_str}"
    params = {
        "sources": sources_str,
        "destinations": dests_str,
        "annotations": "duration,distance"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"code": "Error", "durations": [], "distances": [], "message": str(e)}
