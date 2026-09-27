from pydantic import BaseModel


class ResourcesRequest(BaseModel):
    acuity: str
    facility: str
    extracted: dict = {}
    profile_summary: str | None = None


class ResourceItem(BaseModel):
    item: str
    prob: float


class ResourcesResponse(BaseModel):
    resources: list[ResourceItem]
    model_version: str = ""
    latency_ms: float = 0.0
