from app.util.mock import pick, seed_from_payload, unit_float

LABELS = ["bleeding", "burn", "bruise_fracture", "none_minor"]
SEVERITIES = ["mild", "moderate", "severe"]


def mock_photo_triage(payload: dict) -> dict:
    seed = seed_from_payload(payload)
    v_label = pick(seed, LABELS, "vision_label")
    c_label = pick(seed, LABELS, "classifier_label")
    agreement = v_label == c_label
    return {
        "vision_llm": {"label": v_label, "severity": pick(seed, SEVERITIES, "severity"), "description": "mock vision read", "confidence": round(0.5 + unit_float(seed, "vconf") * 0.4, 2)},
        "finetuned_classifier": {"label": c_label, "confidence": round(0.5 + unit_float(seed, "cconf") * 0.4, 2)},
        "agreement": agreement,
        "needs_review": not agreement,
    }
