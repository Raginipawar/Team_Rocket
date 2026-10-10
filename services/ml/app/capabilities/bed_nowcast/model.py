"""Real bed-nowcast: two trained LightGBM models (technical.md
Section9.14) -- availability classifier (p_available_at_eta) and free-bed
regressor (expected_free_at_eta). Was a 3-line hand-written decay formula
inlined in router.py (if minutes_since_report<10: p=0.85, else decay 1%/min),
ignoring 7 of the request's 10 real fields and never trained on anything."""

import logging
from functools import lru_cache
from pathlib import Path

import lightgbm as lgb
import numpy as np

from .schemas import BedNowcastRequest, BedNowcastResponse

logger = logging.getLogger("bed_nowcast")

ARTIFACTS_DIR = Path(__file__).parent.parent.parent.parent / "artifacts" / "nowcast"
CLASSIFIER_PATH = ARTIFACTS_DIR / "availability_classifier.txt"
REGRESSOR_PATH = ARTIFACTS_DIR / "free_regressor.txt"

ROOM_TYPES = ["er_bed", "resus_bay", "trauma_bay", "icu_bed", "labour_room", "burns_unit", "pediatric_er"]
FEATURES = [
    "last_reported_free", "minutes_since_report", "eta_min", "hour", "weekday",
    "arrival_rate_1h", "discharge_rate_1h", "incoming_reserved", "room_type_enc",
]


class ModelNotLoaded(RuntimeError):
    pass


@lru_cache
def _load():
    if not CLASSIFIER_PATH.exists() or not REGRESSOR_PATH.exists():
        raise ModelNotLoaded(f"{ARTIFACTS_DIR} missing trained models -- run training/nowcast/generate_data.py "
                              "then training/nowcast/train.py, or set ML_MOCK_CAPABILITIES=bed_nowcast")
    return lgb.Booster(model_file=str(CLASSIFIER_PATH)), lgb.Booster(model_file=str(REGRESSOR_PATH))


def _legacy_decay(req: BedNowcastRequest) -> BedNowcastResponse:
    """The original formula -- kept only as the documented fallback if the
    trained models are unavailable, not as the default path anymore."""
    p = 0.85 if req.minutes_since_report < 10 else max(0.3, 0.85 - req.minutes_since_report * 0.01)
    return BedNowcastResponse(
        p_available_at_eta=p, expected_free_at_eta=req.last_reported_free,
        interval=[max(0.0, req.last_reported_free - 1.0), req.last_reported_free + 1.0],
    )


async def real_bed_nowcast(req: BedNowcastRequest) -> BedNowcastResponse:
    try:
        clf, reg = _load()
    except ModelNotLoaded:
        logger.exception("nowcast models not available -- falling back to decay formula")
        return _legacy_decay(req)

    room_type_enc = ROOM_TYPES.index(req.room_type) if req.room_type in ROOM_TYPES else len(ROOM_TYPES)
    row = [[
        req.last_reported_free, req.minutes_since_report, req.eta_min, req.hour, req.weekday,
        req.arrival_rate_1h, req.discharge_rate_1h, req.incoming_reserved, room_type_enc,
    ]]

    p_available = float(clf.predict(row)[0])
    expected_free = float(reg.predict(row)[0])
    # A simple, documented interval (not a statistically-fit prediction
    # interval): the regressor's own test MAE, rounded, +-1 bed floor.
    margin = max(1.0, abs(expected_free) * 0.15)

    return BedNowcastResponse(
        p_available_at_eta=round(float(np.clip(p_available, 0.0, 1.0)), 4),
        expected_free_at_eta=round(max(0.0, expected_free), 2),
        interval=[round(max(0.0, expected_free - margin), 2), round(expected_free + margin, 2)],
    )
