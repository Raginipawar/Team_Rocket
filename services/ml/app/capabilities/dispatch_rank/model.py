"""Real dispatch ranking: LightGBM accept-probability classifier + accept-
latency regressor; score = P(accept) / (eta_sec + E[latency]), with an
ALS-preservation penalty when sending ALS to a stable case while BLS is
available (technical.md §9.6). Trained on simulated driver-behaviour logs
(training/dispatch/train.py, REPORT.json has the real metrics)."""

from functools import lru_cache
from pathlib import Path

import lightgbm as lgb

ARTIFACTS_DIR = Path(__file__).parent.parent.parent.parent / "artifacts" / "dispatch_rank"
FEATURES = ["eta_sec", "distance_m", "hours_on_shift", "mins_since_last_job",
            "accept_rate_7d", "avg_accept_latency_s", "declines_today"]

ALS_PRESERVATION_PENALTY = 0.85  # multiply score by this when ALS is sent to a non-critical case


class ModelNotLoaded(RuntimeError):
    pass


@lru_cache
def _load():
    clf_path = ARTIFACTS_DIR / "accept_classifier.txt"
    reg_path = ARTIFACTS_DIR / "latency_regressor.txt"
    if not clf_path.exists() or not reg_path.exists():
        raise ModelNotLoaded(
            f"{ARTIFACTS_DIR} missing trained models -- run training/dispatch/generate_data.py "
            "then training/dispatch/train.py, or set ML_MOCK_CAPABILITIES=dispatch_rank"
        )
    return lgb.Booster(model_file=str(clf_path)), lgb.Booster(model_file=str(reg_path))


async def real_dispatch_rank(payload: dict) -> dict:
    clf, reg = _load()
    emergency = payload["emergency"]
    candidates = payload["candidates"]

    import pandas as pd
    rows = pd.DataFrame([{f: c.get(f, 0) for f in FEATURES} for c in candidates])
    accept_prob = clf.predict(rows)
    latency = reg.predict(rows)

    required_type = emergency.get("required_type")
    acuity = emergency.get("acuity")

    ranked = []
    for i, c in enumerate(candidates):
        score = accept_prob[i] / (c["eta_sec"] + max(latency[i], 1.0))
        if required_type == "ALS" and c.get("type") == "ALS" and acuity not in ("critical",):
            score *= ALS_PRESERVATION_PENALTY
        ranked.append({
            "ambulance_id": c["ambulance_id"],
            "accept_prob": round(float(accept_prob[i]), 4),
            "expected_accept_latency_s": round(float(max(latency[i], 1.0)), 2),
            "expected_arrival_sec": c["eta_sec"],
            "score": round(float(score), 6),
        })

    ranked.sort(key=lambda r: r["score"], reverse=True)
    return {"ranked": ranked}
