"""Real dispatch ranking: LightGBM accept-probability classifier + accept-latency
regressor; score = P(accept) / (eta_sec + E[latency]) with ALS-preservation
penalty (technical.md §9.6). Trained on simulated driver-behaviour logs."""


class ModelNotLoaded(RuntimeError):
    pass


async def real_dispatch_rank(payload: dict) -> dict:
    raise ModelNotLoaded(
        "dispatch-rank models not trained -- run training/dispatch/train.py, "
        "or set ML_MOCK_CAPABILITIES=dispatch_rank"
    )
