from app.util.mock import pick, seed_from_payload, unit_float

ACUITIES = ["critical", "urgent", "stable"]
FACILITIES = ["cardiac", "stroke", "trauma", "burns", "respiratory",
              "obstetric", "pediatric", "poisoning", "general"]


def mock_triage(payload: dict) -> dict:
    seed = seed_from_payload(payload)
    acuity = pick(seed, ACUITIES, "acuity")
    facility = pick(seed, FACILITIES, "facility")
    confidence = 0.55 + unit_float(seed, "conf") * 0.4  # 0.55-0.95

    acuity_probs = {a: round(0.1, 2) for a in ACUITIES}
    acuity_probs[acuity] = round(confidence, 2)
    facility_probs = {f: round(0.05, 2) for f in FACILITIES}
    facility_probs[facility] = round(confidence, 2)

    extracted = payload.get("extracted", {})
    age = extracted.get("age")
    mechanism = extracted.get("mechanism", "none")
    fragility = bool(extracted.get("pregnant")) or (age is not None and age < 14) or (
        mechanism in ("fall", "road_accident")
    )
    mlc_flag = mechanism in ("road_accident", "assault", "burn", "poisoning")

    return {
        "acuity": acuity,
        "acuity_probs": acuity_probs,
        "facility": facility,
        "facility_probs": facility_probs,
        "confidence": round(confidence, 2),
        "needs_review": confidence < 0.60,
        "fragility": fragility,
        "mlc_flag": mlc_flag,
    }
