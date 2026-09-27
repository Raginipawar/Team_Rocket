from app.util.mock import seed_from_payload, unit_float

ITEMS_BY_FACILITY = {
    "cardiac": ["cardiologist", "defibrillator", "cath_lab", "ecg"],
    "trauma": ["trauma_surgeon", "blood_o_neg", "operating_theatre", "ct_scanner"],
    "stroke": ["neurologist", "ct_scanner", "thrombolysis_kit"],
    "burns": ["burns_surgeon", "burns_unit", "iv_fluids"],
    "obstetric": ["obstetrician", "labour_room"],
    "pediatric": ["pediatrician", "pediatric_er"],
    "general": ["emergency_physician", "er_bed"],
}


def mock_resources(payload: dict) -> dict:
    seed = seed_from_payload(payload)
    items = ITEMS_BY_FACILITY.get(payload.get("facility"), ITEMS_BY_FACILITY["general"])
    return {
        "resources": [
            {"item": item, "prob": round(0.3 + unit_float(seed, item) * 0.65, 2)}
            for item in items
        ]
    }
