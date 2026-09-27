from pydantic import BaseModel
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
