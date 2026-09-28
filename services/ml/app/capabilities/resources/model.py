"""Real resource prediction: LightGBM one-vs-rest, one booster per item,
trained on the mapping.csv clinician-style table + noise (technical.md
§9.10, training/resources/train.py has REPORT.json). Known weak spot,
reported honestly: 'mri' has no real signal in the mapping table (AUC ~0.42,
near random) -- it was never given a modifier condition, so the model just
learned the background rate. Flagged for whoever tunes mapping.csv next,
not silently hidden."""

from functools import lru_cache
from pathlib import Path

import lightgbm as lgb

ARTIFACTS_DIR = Path(__file__).parent.parent.parent.parent / "artifacts" / "resources"
ITEMS = [
    "emergency_physician", "cardiologist", "neurologist", "trauma_surgeon", "burns_surgeon",
    "obstetrician", "pediatrician", "pulmonologist", "anesthetist", "er_nurse",
    "ventilator", "cath_lab", "ct_scanner", "mri", "defibrillator", "dialysis", "operating_theatre",
    "blood_o_neg", "blood_o_pos", "blood_a_pos", "blood_b_pos", "blood_ab_pos",
]
FACILITY_CLASSES = ["burns", "cardiac", "general", "obstetric", "pediatric", "poisoning", "respiratory", "stroke", "trauma"]
ACUITY_CLASSES = ["critical", "stable", "urgent"]
BLEEDING_CLASSES = ["mild", "none", "severe"]


class ModelNotLoaded(RuntimeError):
    pass


@lru_cache
def _load_all():
    boosters = {}
    for item in ITEMS:
        path = ARTIFACTS_DIR / f"{item}.txt"
        if not path.exists():
            raise ModelNotLoaded(
                f"{path} missing -- run training/resources/generate_data.py then "
                "training/resources/train.py, or set ML_MOCK_CAPABILITIES=resources"
            )
        boosters[item] = lgb.Booster(model_file=str(path))
    return boosters


def _encode(value: str, classes: list[str]) -> int:
    return classes.index(value) if value in classes else 0


async def real_resources(payload: dict) -> dict:
    boosters = _load_all()
    extracted = payload.get("extracted", {})

    row = [[
        _encode(payload.get("facility", "general"), FACILITY_CLASSES),
        _encode(payload.get("acuity", "urgent"), ACUITY_CLASSES),
        _encode(extracted.get("bleeding", "none"), BLEEDING_CLASSES),
        int(bool(extracted.get("pregnant", False))),
        extracted.get("age", 35) or 35,
    ]]

    resources = []
    for item, booster in boosters.items():
        prob = float(booster.predict(row)[0])
        resources.append({"item": item, "prob": round(prob, 4)})

    return {"resources": resources}
