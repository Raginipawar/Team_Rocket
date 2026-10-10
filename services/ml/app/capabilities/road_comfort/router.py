from fastapi import APIRouter

from app.config import get_settings

from .mock import get_road_comfort_mock
from .model import real_road_comfort
from .schemas import RoadComfortRequest, RoadComfortResponse

router = APIRouter(prefix="/ml/v1")


@router.post("/road-comfort", response_model=RoadComfortResponse)
async def predict_road_comfort(req: RoadComfortRequest):
    # This capability's request/response are typed Pydantic models (not the
    # dict contract app/util/base_router.resolve expects), so mode selection
    # is inline here rather than forcing an adapter on both sides.
    if get_settings().capability_mode("road_comfort") == "mock":
        return await get_road_comfort_mock(req)
    return await real_road_comfort(req)
