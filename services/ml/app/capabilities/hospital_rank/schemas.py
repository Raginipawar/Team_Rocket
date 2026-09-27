from pydantic import BaseModel
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
