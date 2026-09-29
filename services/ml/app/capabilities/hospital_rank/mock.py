from .schemas import HospitalRankRequest, HospitalRankResponse, Explanation

async def rank_hospitals_mock(req: HospitalRankRequest) -> list[HospitalRankResponse]:
    sorted_candidates = sorted(req.candidates, key=lambda c: c.features.eta_sec)
    res = []
    for i, c in enumerate(sorted_candidates):
        res.append(HospitalRankResponse(
            hospital_id=c.hospital_id,
            score=100.0 - (c.features.eta_sec / 100),
            rank=i + 1,
            explanation=[
                Explanation(factor="eta", value=f"{int(c.features.eta_sec//60)} min", contribution=10.0, text=f"{int(c.features.eta_sec//60)} min ETA")
            ],
            eligible=True
        ))
    return res
