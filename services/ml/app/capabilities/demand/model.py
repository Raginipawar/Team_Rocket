"""Real demand forecast: LightGBM Poisson regression, lags 1/24/168h,
neighbour H3 sums, hour/weekday/festival flags (technical.md §9.15). Trained
on 90 days of synthetic call history (training/demand/train.py, REPORT.json
has the real metrics: MAE 0.163 vs 0.166 historical-average baseline)."""

from functools import lru_cache
from pathlib import Path

import lightgbm as lgb

ARTIFACT_PATH = Path(__file__).parent.parent.parent.parent / "artifacts" / "demand" / "lightgbm_poisson.txt"


class ModelNotLoaded(RuntimeError):
    pass


@lru_cache
def _load():
    if not ARTIFACT_PATH.exists():
        raise ModelNotLoaded(
            f"{ARTIFACT_PATH} missing -- run training/demand/generate_data.py then "
            "training/demand/train.py, or set ML_MOCK_CAPABILITIES=demand"
        )
    return lgb.Booster(model_file=str(ARTIFACT_PATH))


async def real_demand(payload: dict) -> dict:
    """Requires the caller to pass per-cell feature rows (lag_1h, lag_24h,
    lag_168h, neighbour_sum_calls, hour, weekday, is_festival, cell_kind_enc)
    computed from recent call history -- technical.md's GET
    /ml/v1/demand-forecast contract doesn't specify how the caller assembles
    these, so this expects them pre-computed in payload['cells']. Documented
    gap: the real-time feature assembly (B's/A's job that maintains the
    rolling lag windows) isn't built yet -- this only proves the trained
    model serves correctly given features."""
    model = _load()
    cells = payload.get("cells", [])
    if not cells:
        return {"cells": []}

    import pandas as pd
    features = ["hour", "weekday", "is_festival", "lag_1h", "lag_24h", "lag_168h",
                "neighbour_sum_calls", "cell_kind_enc"]
    rows = pd.DataFrame([{f: c.get(f, 0) for f in features} for c in cells])
    preds = model.predict(rows).clip(min=0)

    out = []
    for i, c in enumerate(cells):
        mean = float(preds[i])
        out.append({
            "h3_cell": c["h3_cell"], "predicted_calls": round(mean, 3),
            "lo": round(max(0, mean - 1.5), 3), "hi": round(mean + 1.5, 3),
        })
    return {"cells": out}
