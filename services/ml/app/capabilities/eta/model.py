import uuid
from .schemas import ETARequest, ETAResponse, ETAMatrixRequest, ETAMatrixResponse, Route
from ...geo.osrm_client import route as osrm_route, table as osrm_table
from ..road_comfort.model import get_road_comfort
from ..road_comfort.schemas import RoadComfortRequest

async def get_eta(req: ETARequest) -> ETAResponse:
    osrm_resp = await osrm_route(req.origin, req.destination, alternatives=req.alternatives)
    if osrm_resp.get("code") != "Ok" or not osrm_resp.get("routes"):
        from .mock import get_eta_mock
        return await get_eta_mock(req)
        
    routes = []
    for r in osrm_resp["routes"]:
        distance = r.get("distance", 0.0)
        duration = r.get("duration", 0.0)
        geometry = r.get("geometry", "")
        
        eta_sec = duration
        eta_low = duration * 0.85
        eta_high = duration * 1.25
        
        rc_req = RoadComfortRequest(geometry=geometry)
        rc_resp = await get_road_comfort(rc_req)
        
        route_obj = Route(
            route_id=str(uuid.uuid4()),
            geometry=geometry,
            distance_m=distance,
            eta_sec=eta_sec,
            eta_low_sec=eta_low,
            eta_high_sec=eta_high,
            source="osrm",
            road_comfort=rc_resp.score
        )
        routes.append(route_obj)
        
    return ETAResponse(routes=routes)

async def get_eta_matrix(req: ETAMatrixRequest) -> ETAMatrixResponse:
    osrm_resp = await osrm_table(req.origins, req.destinations)
    if osrm_resp.get("code") != "Ok":
        from .mock import get_eta_matrix_mock
        return await get_eta_matrix_mock(req)
        
    return ETAMatrixResponse(
        durations=osrm_resp.get("durations", []),
        distances=osrm_resp.get("distances", [])
    )
