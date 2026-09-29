from fastapi import APIRouter
from .schemas import MCIAllocateRequest, MCIAllocateResponse, Assignment, Unassigned

router = APIRouter(prefix="/ml/v1")

@router.post("/mci-allocate", response_model=MCIAllocateResponse)
async def get_mci_allocate_route(req: MCIAllocateRequest):
    assignments = []
    unassigned = []
    amb_idx = 0
    hosp_idx = 0
    
    for p in req.patients:
        if amb_idx < len(req.ambulances) and hosp_idx < len(req.hospitals):
            assignments.append(Assignment(
                patient_id=p.id,
                ambulance_id=req.ambulances[amb_idx].id,
                hospital_id=req.hospitals[hosp_idx].id
            ))
            amb_idx += 1
            hosp_idx = (hosp_idx + 1) % len(req.hospitals)
        else:
            unassigned.append(Unassigned(patient_id=p.id, reason="No available resources"))
            
    return MCIAllocateResponse(
        assignments=assignments,
        unassigned=unassigned,
        objective=100.0
    )
