from .schemas import ETARequest, ETAResponse, ETAMatrixRequest, ETAMatrixResponse
from .mock import get_eta_mock, get_eta_matrix_mock

async def get_eta(req: ETARequest) -> ETAResponse:
    return await get_eta_mock(req)

async def get_eta_matrix(req: ETAMatrixRequest) -> ETAMatrixResponse:
    return await get_eta_matrix_mock(req)
