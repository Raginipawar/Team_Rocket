from .schemas import HospitalRankRequest, HospitalRankResponse
from .mock import rank_hospitals_mock

async def rank_hospitals(req: HospitalRankRequest) -> list[HospitalRankResponse]:
    return await rank_hospitals_mock(req)
