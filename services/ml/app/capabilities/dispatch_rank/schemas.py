from pydantic import BaseModel


class EmergencyForRank(BaseModel):
    location: dict  # {lat, lng}
    acuity: str
    required_type: str  # BLS | ALS


class Candidate(BaseModel):
    ambulance_id: str
    type: str
    eta_sec: int
    distance_m: float
    hours_on_shift: float
    mins_since_last_job: float
    accept_rate_7d: float
    avg_accept_latency_s: float
    declines_today: int


class DispatchRankRequest(BaseModel):
    emergency: EmergencyForRank
    candidates: list[Candidate]


class RankedCandidate(BaseModel):
    ambulance_id: str
    accept_prob: float
    expected_accept_latency_s: float
    expected_arrival_sec: int
    score: float


class DispatchRankResponse(BaseModel):
    # technical.md §9.6 shows a bare sorted array; wrapped here so model_version/
    # latency_ms (required on every ML response per §9) have somewhere to live.
    # Flag with B/C at contract freeze if the bare-array shape is required instead.
    ranked: list[RankedCandidate]
    model_version: str = ""
    latency_ms: float = 0.0
