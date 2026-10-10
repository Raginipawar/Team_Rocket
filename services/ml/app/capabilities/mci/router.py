import logging

from fastapi import APIRouter

from .model import SolverFailed, real_mci_allocate
from .schemas import Assignment, MCIAllocateRequest, MCIAllocateResponse, Unassigned

logger = logging.getLogger("mci")
router = APIRouter(prefix="/ml/v1")


def _round_robin_fallback(req: MCIAllocateRequest) -> MCIAllocateResponse:
    """Documented fallback only (ignores acuity/ETA/capacity) -- used if the
    real OR-Tools solver fails, not the default path anymore."""
    assignments, unassigned = [], []
    amb_idx, hosp_idx = 0, 0
    for p in req.patients:
        if amb_idx < len(req.ambulances) and hosp_idx < len(req.hospitals):
            assignments.append(Assignment(patient_id=p.id, ambulance_id=req.ambulances[amb_idx].id,
                                           hospital_id=req.hospitals[hosp_idx].id))
            amb_idx += 1
            hosp_idx = (hosp_idx + 1) % len(req.hospitals)
        else:
            unassigned.append(Unassigned(patient_id=p.id, reason="no_available_resources"))
    return MCIAllocateResponse(assignments=assignments, unassigned=unassigned, objective=0.0)


@router.post("/mci-allocate", response_model=MCIAllocateResponse)
async def get_mci_allocate_route(req: MCIAllocateRequest):
    try:
        return await real_mci_allocate(req)
    except SolverFailed:
        logger.exception("mci solver failed -- falling back to round-robin")
        return _round_robin_fallback(req)
