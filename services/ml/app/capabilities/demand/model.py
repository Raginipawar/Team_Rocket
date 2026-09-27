"""Real demand forecast: LightGBM Poisson regression, lags 1/24/168h, neighbour
H3 sums, hour/weekday, OSM POI density (technical.md §9.15). Trained on
synthetic 90-day call history with realistic spatio-temporal patterns."""


class ModelNotLoaded(RuntimeError):
    pass


async def real_demand(payload: dict) -> dict:
    raise ModelNotLoaded(
        "demand-forecast LightGBM model not trained -- run training data gen "
        "in services/ml/data/demand/, or set ML_MOCK_CAPABILITIES=demand"
    )
