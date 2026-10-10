"""Real hospital ranking: trained LightGBM LambdaRank model (technical.md
Section9.13), with real per-prediction explanations via LightGBM's native
pred_contrib (TreeSHAP-equivalent, no external `shap` dependency -- see
training/hospital_rank/train.py for why). Was a pure pass-through to the
mock (sort-by-eta_sec, no explanation ever generated)."""

import logging
from functools import lru_cache
from pathlib import Path

import lightgbm as lgb

from .schemas import Candidate, Explanation, HospitalRankRequest, HospitalRankResponse

logger = logging.getLogger("hospital_rank")

ARTIFACT_PATH = Path(__file__).parent.parent.parent.parent / "artifacts" / "hospital_rank" / "lambdarank.txt"

FEATURES = [
    "facility_match", "required_resources_available_prob", "p_bed_available_at_eta",
    "eta_sec", "eta_high_sec", "road_comfort", "specialist_on_duty_at_eta",
    "staleness_min", "occupancy_ratio", "rejection_rate_24h", "incoming_reserved_count",
    "stabilization_capable", "fragility_high", "fragility_medium",
]

# Human-readable explanation templates per feature, filled with the
# candidate's own value -- technical.md Section9.13's "Cath lab available",
# "Data 3 min old", "11 min ETA" style.
EXPLANATION_TEXT = {
    "facility_match": lambda v, c: "Matches required facility type" if v else "Facility type does not match",
    "eta_sec": lambda v, c: f"{int(v // 60)} min ETA",
    "eta_high_sec": lambda v, c: f"Up to {int(v // 60)} min ETA in traffic",
    "required_resources_available_prob": lambda v, c: f"{int(v * 100)}% chance required specialist/equipment is available",
    "p_bed_available_at_eta": lambda v, c: f"{int(v * 100)}% chance a bed is free on arrival",
    "road_comfort": lambda v, c: f"Road comfort score {v:.0f}/100",
    "specialist_on_duty_at_eta": lambda v, c: f"{int(v * 100)}% chance specialist on duty at ETA",
    "staleness_min": lambda v, c: f"Hospital data {v:.0f} min old",
    "occupancy_ratio": lambda v, c: f"{int(v * 100)}% occupied",
    "rejection_rate_24h": lambda v, c: f"{int(v * 100)}% rejection rate in last 24h",
    "incoming_reserved_count": lambda v, c: f"{int(v)} other ambulances already inbound",
    "stabilization_capable": lambda v, c: "Can stabilize en route" if v else "Cannot stabilize en route",
    "fragility_high": lambda v, c: "High-fragility patient" if v else None,
    "fragility_medium": lambda v, c: "Medium-fragility patient" if v else None,
}


class ModelNotLoaded(RuntimeError):
    pass


@lru_cache
def _load():
    if not ARTIFACT_PATH.exists():
        raise ModelNotLoaded(
            f"{ARTIFACT_PATH} missing -- run training/hospital_rank/generate_data.py then "
            "training/hospital_rank/train.py, or set ML_MOCK_CAPABILITIES=hospital_rank"
        )
    return lgb.Booster(model_file=str(ARTIFACT_PATH))


def _row_for(c: Candidate) -> dict:
    f = c.features
    return {
        "facility_match": int(f.facility_match),
        "required_resources_available_prob": f.required_resources_available_prob,
        "p_bed_available_at_eta": f.p_bed_available_at_eta,
        "eta_sec": f.eta_sec, "eta_high_sec": f.eta_high_sec, "road_comfort": f.road_comfort,
        "specialist_on_duty_at_eta": f.specialist_on_duty_at_eta, "staleness_min": f.staleness_min,
        "occupancy_ratio": f.occupancy_ratio, "rejection_rate_24h": f.rejection_rate_24h,
        "incoming_reserved_count": f.incoming_reserved_count,
        "stabilization_capable": int(f.stabilization_capable),
        "fragility_high": int(f.fragility == "high"), "fragility_medium": int(f.fragility == "medium"),
    }


def _explain(row: dict, shap_row) -> list[Explanation]:
    """Top-3 contributing factors by |SHAP value|, templated into real text."""
    contributions = sorted(zip(FEATURES, shap_row[:-1]), key=lambda kv: -abs(kv[1]))
    explanations = []
    for feature, contribution in contributions:
        if len(explanations) >= 3:
            break
        text = EXPLANATION_TEXT[feature](row[feature], row)
        if text is None:  # e.g. fragility_high template returns None when the flag is 0
            continue
        explanations.append(Explanation(
            factor=feature, value=str(row[feature]), contribution=round(float(contribution), 2), text=text,
        ))
    return explanations


async def rank_hospitals(req: HospitalRankRequest) -> list[HospitalRankResponse]:
    try:
        model = _load()
    except ModelNotLoaded:
        logger.exception("hospital_rank model not available -- falling back to mock")
        from .mock import rank_hospitals_mock
        return await rank_hospitals_mock(req)

    import pandas as pd

    rows = [_row_for(c) for c in req.candidates]
    df = pd.DataFrame(rows)[FEATURES]
    scores = model.predict(df)
    shap_matrix = model.predict(df, pred_contrib=True)

    results = []
    for i, c in enumerate(req.candidates):
        results.append((c, float(scores[i]), _explain(rows[i], shap_matrix[i])))

    results.sort(key=lambda r: -r[1])
    return [
        HospitalRankResponse(hospital_id=c.hospital_id, score=round(score, 3), rank=rank + 1,
                              explanation=explanation, eligible=True)
        for rank, (c, score, explanation) in enumerate(results)
    ]
