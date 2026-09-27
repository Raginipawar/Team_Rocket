from fastapi import APIRouter, Depends
from .schemas import ETARequest, ETAResponse, ETAMatrixRequest, ETAMatrixResponse
from .model import get_eta, get_eta_matrix

router = APIRouter(prefix="/ml/v1")

@router.post("/eta", response_model=ETAResponse)
async def predict_eta(req: ETARequest):
    return await get_eta(req)

@router.post("/eta/matrix", response_model=ETAMatrixResponse)
async def predict_eta_matrix(req: ETAMatrixRequest):
    return await get_eta_matrix(req)
