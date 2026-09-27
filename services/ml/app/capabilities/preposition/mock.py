from app.util.mock import seed_from_payload, unit_float


def mock_preposition(payload: dict) -> dict:
    seed = seed_from_payload(payload)
    suggestions = []
    for i, amb in enumerate(payload.get("idle_ambulances", [])):
        loc = amb["location"]
        suggestions.append({
            "ambulance_id": amb["id"],
            "target": {
                "lat": loc["lat"] + (unit_float(seed, f"dlat{i}") - 0.5) * 0.02,
                "lng": loc["lng"] + (unit_float(seed, f"dlng{i}") - 0.5) * 0.02,
            },
            "h3_cell": f"88{i:x}2a34fffffff",
            "expected_coverage_gain": round(unit_float(seed, f"gain{i}") * 0.3, 3),
        })
    return {"suggestions": suggestions}
