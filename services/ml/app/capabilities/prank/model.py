"""Real prank scoring: Isolation Forest trained on simulated caller-behaviour
logs (technical.md §9.4). Threshold set at 5% FPR on legit validation data
(training/prank/train.py, REPORT.json has the real metrics). Policy (never
block; critical bypasses verification) lives in core, not here."""

from functools import lru_cache
from pathlib import Path

import joblib

ARTIFACT_PATH = Path(__file__).parent.parent.parent.parent / "artifacts" / "prank" / "isolation_forest.joblib"


class ModelNotLoaded(RuntimeError):
    pass


@lru_cache
def _load():
    if not ARTIFACT_PATH.exists():
        raise ModelNotLoaded(
            f"{ARTIFACT_PATH} not found -- run training/prank/generate_data.py "
            "then training/prank/train.py, or set ML_MOCK_CAPABILITIES=prank"
        )
    return joblib.load(ARTIFACT_PATH)


def _reasons(payload: dict) -> list[str]:
    reasons = []
    if payload.get("calls_24h", 0) > 3:
        reasons.append("high call frequency in 24h")
    if payload.get("coherence", 1.0) < 0.3:
        reasons.append("low transcript coherence")
    if payload.get("prior_prank_flags", 0) > 0:
        reasons.append("prior prank flags on this phone")
    if payload.get("location_jump_km", 0) > 10:
        reasons.append("large location jump between calls")
    if payload.get("text_repeat_ratio", 0) > 0.6:
        reasons.append("repeated stock phrases")
    return reasons


async def real_prank(payload: dict) -> dict:
    bundle = _load()
    model, threshold, features = bundle["model"], bundle["threshold"], bundle["features"]

    import pandas as pd
    row = pd.DataFrame([[payload.get(f, 0) for f in features]], columns=features)
    raw_score = -model.decision_function(row)[0]
    score = max(0.0, min(1.0, (raw_score - (-0.2)) / (0.4 - (-0.2))))  # rescale to a rough 0-1 band around the threshold
    suspicious = raw_score >= threshold

    return {"score": round(float(score), 4), "suspicious": bool(suspicious), "reasons": _reasons(payload)}
