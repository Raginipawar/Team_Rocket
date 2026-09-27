import math
from .schemas import ETARequest, ETAResponse, Route, ETAMatrixRequest, ETAMatrixResponse
import uuid

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # radius of Earth in meters
    phi_1 = math.radians(lat1)
    phi_2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi_1) * math.cos(phi_2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

async def get_eta_mock(req: ETARequest) -> ETAResponse:
    dist = haversine(req.origin.lat, req.origin.lng, req.destination.lat, req.destination.lng)
    speed = 11.11 # 40 km/h
    eta = dist / speed
    eta_low = eta * 0.8
    eta_high = eta * 1.2
    route = Route(
        route_id=str(uuid.uuid4()),
        geometry="mock_polyline",
        distance_m=dist,
        eta_sec=eta,
        eta_low_sec=eta_low,
        eta_high_sec=eta_high,
        source="mock_haversine",
        road_comfort=75.0
    )
    return ETAResponse(routes=[route])

async def get_eta_matrix_mock(req: ETAMatrixRequest) -> ETAMatrixResponse:
    durations = []
    distances = []
    for o in req.origins:
        d_row = []
        dur_row = []
        for d in req.destinations:
            dist = haversine(o.lat, o.lng, d.lat, d.lng)
            d_row.append(dist)
            dur_row.append(dist / 11.11)
        durations.append(dur_row)
        distances.append(d_row)
    return ETAMatrixResponse(durations=durations, distances=distances)
