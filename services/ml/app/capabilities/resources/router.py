from fastapi import APIRouter

from app.util.base_router import resolve

from .mock import mock_resources
from .model import real_resources
from .schemas import ResourcesRequest, ResourcesResponse

router = APIRouter()


@router.post("/resources", response_model=ResourcesResponse)
async def resources(req: ResourcesRequest) -> dict:
    return await resolve("resources", real_resources, mock_resources, req.model_dump())
