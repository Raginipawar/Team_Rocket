from pydantic import BaseModel
from typing import List, Dict

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
