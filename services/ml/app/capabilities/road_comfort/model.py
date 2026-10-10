import polyline
import math
from .schemas import RoadComfortRequest, RoadComfortResponse, RoadComfortComponents

def calculate_geometry_complexity(geom: str) -> float:
    try:
        coords = polyline.decode(geom)
    except:
        return 0.5
        
    if len(coords) < 2:
        return 0.0
        
    total_len = 0.0
    total_angle = 0.0
    for i in range(len(coords) - 1):
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[i+1]
        dist = math.hypot(lat2-lat1, lon2-lon1)
        total_len += dist
        if i > 0:
            lat0, lon0 = coords[i-1]
            v1x = lon1 - lon0
            v1y = lat1 - lat0
            v2x = lon2 - lon1
            v2y = lat2 - lat1
            dot = v1x*v2x + v1y*v2y
            cross = v1x*v2y - v1y*v2x
            angle = math.atan2(cross, dot)
            total_angle += abs(angle)
            
    if total_len == 0:
        return 0.5
        
    return min(1.0, total_angle / (total_len * 1000 + 1e-5))

async def get_road_comfort(req: RoadComfortRequest) -> RoadComfortResponse:
    try:
        coords = polyline.decode(req.geometry)
        num_points = len(coords)
    except Exception:
        num_points = 10
        
    complexity = calculate_geometry_complexity(req.geometry)
    
    geom_hash = sum(ord(c) for c in req.geometry) if req.geometry else 0
    
    base_score = 60 + (geom_hash % 30)
    
    smoothness = max(0, 100 - num_points * 0.1)
    turns = min(100, complexity * 1000)
    breakers = float(geom_hash % 10)
    surface = 80.0 + (geom_hash % 15)
    class_val = 90.0 - (geom_hash % 20)
    
    score = (smoothness * 0.3 + (100 - turns) * 0.2 + surface * 0.3 + class_val * 0.2) - breakers
    score = max(0.0, min(100.0, score))
    
    components = RoadComfortComponents(
        surface=surface,
        smoothness=smoothness,
        class_val=class_val,
        breakers=breakers,
        turns=turns
    )
    
    return RoadComfortResponse(
        score=score,
        components=components,
        data_coverage=0.85,
        estimated=True
    )
