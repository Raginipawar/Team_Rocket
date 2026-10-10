from fastapi import APIRouter
from .schemas import MCIAllocateRequest, MCIAllocateResponse
from .model import allocate_mci

router = APIRouter()

@router.post("/mci-allocate", response_model=MCIAllocateResponse)
async def get_mci_allocate_route(req: MCIAllocateRequest):
    return await allocate_mci(req)
