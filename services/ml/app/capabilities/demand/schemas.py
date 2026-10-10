from pydantic import BaseModel


class DemandCellFeatures(BaseModel):
    """Per-cell input features real_demand() actually needs (lag_1h/24h/168h
    etc.) -- the router previously only accepted horizon_min and threw these
    away entirely, so a GET to this endpoint always returned {"cells": []}
    via real_demand's own empty-cells short-circuit. The caller (a periodic
    job, Section2.10/A16) is expected to compute these from recent real call
    history per H3 cell."""
    h3_cell: str
    hour: int = 0
    weekday: int = 0
    is_festival: int = 0
    lag_1h: float = 0.0
    lag_24h: float = 0.0
    lag_168h: float = 0.0
    neighbour_sum_calls: float = 0.0
    cell_kind_enc: int = 0


class DemandForecastRequest(BaseModel):
    horizon_min: int = 60
    cells: list[DemandCellFeatures] = []


class DemandCell(BaseModel):
    h3_cell: str
    predicted_calls: float
    lo: float
    hi: float


class DemandForecastResponse(BaseModel):
    cells: list[DemandCell]
    model_version: str = ""
    latency_ms: float = 0.0
