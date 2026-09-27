from app.util.mock import pick, seed_from_payload, unit_float

SYMPTOM_SETS = [
    ["chest_pain", "sweating", "breathlessness"],
    ["bleeding", "unconscious"],
    ["fever", "vomiting"],
]
MECHANISMS = ["none", "road_accident", "fall", "assault", "burn", "poisoning", "drowning", "other"]


def mock_extract(payload: dict) -> dict:
    seed = seed_from_payload(payload)
    return {
        "age": 20 + int(unit_float(seed, "age") * 60),
        "age_confidence": pick(seed, ["stated", "estimated", "unknown"], "age_conf"),
        "sex": pick(seed, ["M", "F"], "sex"),
        "patient_count": 1,
        "conscious": unit_float(seed, "conscious") > 0.2,
        "breathing": pick(seed, ["normal", "difficult", "absent"], "breathing"),
        "bleeding": pick(seed, ["none", "mild", "severe"], "bleeding"),
        "symptoms": pick(seed, SYMPTOM_SETS, "symptoms"),
        "mechanism": pick(seed, MECHANISMS, "mechanism"),
        "pregnant": unit_float(seed, "pregnant") > 0.9,
        "landmark": None,
        "for_whom": pick(seed, ["self", "father", "mother", "stranger"], "for_whom"),
        "coherence": round(0.5 + unit_float(seed, "coherence") * 0.5, 2),
    }
