from .schemas import RoadComfortRequest, RoadComfortResponse, RoadComfortComponents

async def get_road_comfort_mock(req: RoadComfortRequest) -> RoadComfortResponse:
    return RoadComfortResponse(
        score=75.0,
        components=RoadComfortComponents(surface=0, smoothness=0, class_val=0, breakers=0, turns=0),
        data_coverage=0.5,
        estimated=True
    )
