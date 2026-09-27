from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_demand
from .model import real_demand
from .schemas import DemandForecastResponse

router = APIRouter()


@router.get("/demand-forecast", response_model=DemandForecastResponse)
async def demand_forecast(horizon_min: int = 60) -> dict:
    return await resolve("demand", real_demand, mock_demand, {"horizon_min": horizon_min})
