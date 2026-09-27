from fastapi import APIRouter
from .schemas import RoadComfortRequest, RoadComfortResponse
from .mock import get_road_comfort_mock

router = APIRouter(prefix="/ml/v1")

@router.post("/road-comfort", response_model=RoadComfortResponse)
async def predict_road_comfort(req: RoadComfortRequest):
    return await get_road_comfort_mock(req)
