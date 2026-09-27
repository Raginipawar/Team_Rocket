from app.util.mock import seed_from_payload, unit_float


def mock_duplicate(payload: dict) -> dict:
    seed = seed_from_payload(payload)
    candidates = payload.get("candidates", [])
    if not candidates:
        return {"duplicate_of": None, "similarity": 0.0, "same_incident": False, "additional_patients": False}

    similarity = unit_float(seed, "sim")
    is_dup = similarity >= 0.80
    return {
        "duplicate_of": candidates[0]["emergency_id"] if is_dup else None,
        "similarity": round(similarity, 2),
        "same_incident": is_dup,
        "additional_patients": is_dup and unit_float(seed, "extra") > 0.7,
    }
