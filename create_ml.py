import os
from pathlib import Path

base_dir = Path("e:/vit/vit shit/ty/5th sem/hack matrix/Team_Rocket")

files_to_create = {
    # 1. ETA
    "services/ml/app/capabilities/eta/__init__.py": "",
    "services/ml/app/capabilities/eta/schemas.py": """from pydantic import BaseModel
from typing import List, Optional

class Point(BaseModel):
    lat: float
    lng: float

class ETARequest(BaseModel):
    origin: Point
    destination: Point
    depart_at: Optional[str] = None
    alternatives: bool = False

class Route(BaseModel):
    route_id: str
    geometry: str
    distance_m: float
    eta_sec: float
    eta_low_sec: float
    eta_high_sec: float
    source: str
    road_comfort: Optional[float] = None

class ETAResponse(BaseModel):
    routes: List[Route]

class ETAMatrixRequest(BaseModel):
    origins: List[Point]
    destinations: List[Point]

class ETAMatrixResponse(BaseModel):
    durations: List[List[float]]
    distances: List[List[float]]
""",
    "services/ml/app/capabilities/eta/mock.py": """import math
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
    # 40 km/h = 11.11 m/s
    speed = 11.11
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
""",
    "services/ml/app/capabilities/eta/model.py": """from .schemas import ETARequest, ETAResponse, ETAMatrixRequest, ETAMatrixResponse
from .mock import get_eta_mock, get_eta_matrix_mock

# For this stub, we call mock directly. In prod, call OSRM and Mapbox.
async def get_eta(req: ETARequest) -> ETAResponse:
    return await get_eta_mock(req)

async def get_eta_matrix(req: ETAMatrixRequest) -> ETAMatrixResponse:
    return await get_eta_matrix_mock(req)
""",
    "services/ml/app/capabilities/eta/router.py": """from fastapi import APIRouter, Depends
from .schemas import ETARequest, ETAResponse, ETAMatrixRequest, ETAMatrixResponse
from .model import get_eta, get_eta_matrix

router = APIRouter(prefix="/ml/v1")

@router.post("/eta", response_model=ETAResponse)
async def predict_eta(req: ETARequest):
    return await get_eta(req)

@router.post("/eta/matrix", response_model=ETAMatrixResponse)
async def predict_eta_matrix(req: ETAMatrixRequest):
    return await get_eta_matrix(req)
""",

    # 2. Road Comfort
    "services/ml/app/capabilities/road_comfort/__init__.py": "",
    "services/ml/app/capabilities/road_comfort/schemas.py": """from pydantic import BaseModel

class RoadComfortRequest(BaseModel):
    geometry: str

class RoadComfortComponents(BaseModel):
    surface: float
    smoothness: float
    class_val: float
    breakers: float
    turns: float

class RoadComfortResponse(BaseModel):
    score: float
    components: RoadComfortComponents
    data_coverage: float
    estimated: bool
""",
    "services/ml/app/capabilities/road_comfort/mock.py": """from .schemas import RoadComfortRequest, RoadComfortResponse, RoadComfortComponents

async def get_road_comfort_mock(req: RoadComfortRequest) -> RoadComfortResponse:
    return RoadComfortResponse(
        score=75.0,
        components=RoadComfortComponents(surface=0, smoothness=0, class_val=0, breakers=0, turns=0),
        data_coverage=0.5,
        estimated=True
    )
""",
    "services/ml/app/capabilities/road_comfort/model.py": """from .schemas import RoadComfortRequest, RoadComfortResponse
from .mock import get_road_comfort_mock

async def get_road_comfort(req: RoadComfortRequest) -> RoadComfortResponse:
    return await get_road_comfort_mock(req)
""",
    "services/ml/app/capabilities/road_comfort/router.py": """from fastapi import APIRouter
from .schemas import RoadComfortRequest, RoadComfortResponse
from .model import get_road_comfort

router = APIRouter(prefix="/ml/v1")

@router.post("/road-comfort", response_model=RoadComfortResponse)
async def predict_road_comfort(req: RoadComfortRequest):
    return await get_road_comfort(req)
""",

    # 3. Hospital Rank
    "services/ml/app/capabilities/hospital_rank/__init__.py": "",
    "services/ml/app/capabilities/hospital_rank/schemas.py": """from pydantic import BaseModel
from typing import List, Optional

class Emergency(BaseModel):
    acuity: str
    facility: str
    fragility: str
    required_resources: List[str]

class HospitalFeatures(BaseModel):
    facility_match: bool
    required_resources_available_prob: float
    p_bed_available_at_eta: float
    eta_sec: float
    eta_high_sec: float
    road_comfort: float
    specialist_on_duty_at_eta: float
    staleness_min: float
    occupancy_ratio: float
    rejection_rate_24h: float
    incoming_reserved_count: int
    stabilization_capable: bool
    fragility: str

class Candidate(BaseModel):
    hospital_id: str
    features: HospitalFeatures

class HospitalRankRequest(BaseModel):
    emergency: Emergency
    candidates: List[Candidate]

class Explanation(BaseModel):
    factor: str
    value: str
    contribution: float
    text: str

class HospitalRankResponse(BaseModel):
    hospital_id: str
    score: float
    rank: int
    explanation: List[Explanation]
    eligible: bool
    ineligible_reason: Optional[str] = None
""",
    "services/ml/app/capabilities/hospital_rank/mock.py": """from .schemas import HospitalRankRequest, HospitalRankResponse, Explanation

async def rank_hospitals_mock(req: HospitalRankRequest) -> list[HospitalRankResponse]:
    sorted_candidates = sorted(req.candidates, key=lambda c: c.features.eta_sec)
    res = []
    for i, c in enumerate(sorted_candidates):
        res.append(HospitalRankResponse(
            hospital_id=c.hospital_id,
            score=100.0 - (c.features.eta_sec / 100),
            rank=i + 1,
            explanation=[
                Explanation(factor="eta", value=f"{int(c.features.eta_sec//60)} min", contribution=10.0, text=f"{int(c.features.eta_sec//60)} min ETA")
            ],
            eligible=True
        ))
    return res
""",
    "services/ml/app/capabilities/hospital_rank/model.py": """from .schemas import HospitalRankRequest, HospitalRankResponse
from .mock import rank_hospitals_mock

async def rank_hospitals(req: HospitalRankRequest) -> list[HospitalRankResponse]:
    return await rank_hospitals_mock(req)
""",
    "services/ml/app/capabilities/hospital_rank/router.py": """from fastapi import APIRouter
from .schemas import HospitalRankRequest, HospitalRankResponse
from .model import rank_hospitals

router = APIRouter(prefix="/ml/v1")

@router.post("/hospital-rank", response_model=list[HospitalRankResponse])
async def rank_hospitals_route(req: HospitalRankRequest):
    return await rank_hospitals(req)
""",

    # 4. Bed Nowcast
    "services/ml/app/capabilities/bed_nowcast/__init__.py": "",
    "services/ml/app/capabilities/bed_nowcast/schemas.py": """from pydantic import BaseModel
from typing import List

class BedNowcastRequest(BaseModel):
    hospital_id: str
    room_type: str
    last_reported_free: int
    minutes_since_report: float
    eta_min: float
    hour: int
    weekday: int
    arrival_rate_1h: float
    discharge_rate_1h: float
    incoming_reserved: int

class BedNowcastResponse(BaseModel):
    p_available_at_eta: float
    expected_free_at_eta: float
    interval: List[float]
""",
    "services/ml/app/capabilities/bed_nowcast/mock.py": """from .schemas import BedNowcastRequest, BedNowcastResponse

async def get_bed_nowcast_mock(req: BedNowcastRequest) -> BedNowcastResponse:
    if req.minutes_since_report < 10:
        p = 0.85
    else:
        p = max(0.3, 0.85 - req.minutes_since_report * 0.01)
    
    return BedNowcastResponse(
        p_available_at_eta=p,
        expected_free_at_eta=req.last_reported_free,
        interval=[max(0.0, req.last_reported_free - 1.0), req.last_reported_free + 1.0]
    )
""",
    "services/ml/app/capabilities/bed_nowcast/model.py": """from .schemas import BedNowcastRequest, BedNowcastResponse
from .mock import get_bed_nowcast_mock

async def get_bed_nowcast(req: BedNowcastRequest) -> BedNowcastResponse:
    return await get_bed_nowcast_mock(req)
""",
    "services/ml/app/capabilities/bed_nowcast/router.py": """from fastapi import APIRouter
from .schemas import BedNowcastRequest, BedNowcastResponse
from .model import get_bed_nowcast

router = APIRouter(prefix="/ml/v1")

@router.post("/bed-nowcast", response_model=BedNowcastResponse)
async def get_bed_nowcast_route(req: BedNowcastRequest):
    return await get_bed_nowcast(req)
""",

    # 5. MCI Allocate
    "services/ml/app/capabilities/mci/__init__.py": "",
    "services/ml/app/capabilities/mci/schemas.py": """from pydantic import BaseModel
from typing import List, Dict, Optional

class Patient(BaseModel):
    id: str
    acuity: str
    facility: str

class Hospital(BaseModel):
    id: str
    capacities_by_type: Dict[str, int]
    eta_sec: float

class Ambulance(BaseModel):
    id: str
    type: str
    eta_to_scene: float

class MCIAllocateRequest(BaseModel):
    patients: List[Patient]
    hospitals: List[Hospital]
    ambulances: List[Ambulance]

class Assignment(BaseModel):
    patient_id: str
    ambulance_id: str
    hospital_id: str

class Unassigned(BaseModel):
    patient_id: str
    reason: str

class MCIAllocateResponse(BaseModel):
    assignments: List[Assignment]
    unassigned: List[Unassigned]
    objective: float
""",
    "services/ml/app/capabilities/mci/mock.py": """from .schemas import MCIAllocateRequest, MCIAllocateResponse, Assignment, Unassigned

async def allocate_mci_mock(req: MCIAllocateRequest) -> MCIAllocateResponse:
    assignments = []
    unassigned = []
    amb_idx = 0
    hosp_idx = 0
    
    # greedy assignment
    for p in req.patients:
        if amb_idx < len(req.ambulances) and hosp_idx < len(req.hospitals):
            assignments.append(Assignment(
                patient_id=p.id,
                ambulance_id=req.ambulances[amb_idx].id,
                hospital_id=req.hospitals[hosp_idx].id
            ))
            amb_idx += 1
            # Round robin hospitals
            hosp_idx = (hosp_idx + 1) % len(req.hospitals)
        else:
            unassigned.append(Unassigned(patient_id=p.id, reason="No available resources"))
            
    return MCIAllocateResponse(
        assignments=assignments,
        unassigned=unassigned,
        objective=100.0
    )
""",
    "services/ml/app/capabilities/mci/model.py": """from .schemas import MCIAllocateRequest, MCIAllocateResponse
from .mock import allocate_mci_mock

async def allocate_mci(req: MCIAllocateRequest) -> MCIAllocateResponse:
    # use CP-SAT here
    return await allocate_mci_mock(req)
""",
    "services/ml/app/capabilities/mci/router.py": """from fastapi import APIRouter
from .schemas import MCIAllocateRequest, MCIAllocateResponse
from .model import allocate_mci

router = APIRouter(prefix="/ml/v1")

@router.post("/mci-allocate", response_model=MCIAllocateResponse)
async def get_mci_allocate_route(req: MCIAllocateRequest):
    return await allocate_mci(req)
""",

    # Geo
    "services/ml/app/geo/__init__.py": """from .osrm_client import route, table
from .mapbox_client import directions_traffic
""",
    "services/ml/app/geo/osrm_client.py": """import httpx
import os

OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5000")

async def route(origin, destination, alternatives=True) -> dict:
    return {"code": "Ok", "routes": []}

async def table(origins: list, destinations: list) -> dict:
    return {"code": "Ok", "durations": [], "distances": []}
""",
    "services/ml/app/geo/mapbox_client.py": """import httpx
import os

MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", "")

async def directions_traffic(origin, destination) -> dict | None:
    try:
        return {"code": "Ok", "routes": []}
    except Exception:
        return None
""",
    "services/ml/app/geo/edges_store.py": """class EdgesStore:
    def __init__(self, parquet_path: str):
        self.parquet_path = parquet_path
        
    def get_comfort_for_nodes(self, node_pairs: list[tuple[int,int]]) -> list[dict]:
        return [{"score": 75.0} for _ in node_pairs]
""",

    # Training Scripts
    "services/ml/training/eta/collect.py": """# Script to sample OD pairs
print("Collecting ETA data...")
""",
    "services/ml/training/hospital_rank/UTILITY.md": """# Utility Function
ETA + p_no_bed*reroute_delay + p_no_specialist*specialist_delay
""",
    "services/ml/training/hospital_rank/generate_data.py": """# Generate hospital rank synthetic data
print("Generating hospital rank data...")
""",
    "services/ml/training/nowcast/generate_data.py": """# Generate nowcast data
print("Generating nowcast data...")
""",
    "services/ml/training/mci/unit_tests.py": """import unittest

class TestMCI(unittest.TestCase):
    def test_basic(self):
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
"""
}

for rel_path, content in files_to_create.items():
    file_path = base_dir / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

print("Created all files successfully.")
