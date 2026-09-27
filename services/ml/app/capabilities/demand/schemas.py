from pydantic import BaseModel


class DemandCell(BaseModel):
    h3_cell: str
    predicted_calls: float
    lo: float
    hi: float


class DemandForecastResponse(BaseModel):
    cells: list[DemandCell]
    model_version: str = ""
    latency_ms: float = 0.0
