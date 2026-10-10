from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_demand
from .model import real_demand
from .schemas import DemandForecastRequest, DemandForecastResponse

router = APIRouter()


@router.post("/demand-forecast", response_model=DemandForecastResponse)
async def demand_forecast(req: DemandForecastRequest = DemandForecastRequest()) -> dict:
    # Was GET with only horizon_min -- real_demand() needs per-cell lag
    # features, which that contract had nowhere to carry, so every real call
    # silently returned {"cells": []} via real_demand's own empty-cells
    # short-circuit. Now POST, carrying the features the model actually uses.
    return await resolve("demand", real_demand, mock_demand, req.model_dump())
