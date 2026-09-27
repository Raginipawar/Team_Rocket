from app.util.mock import seed_from_payload, unit_float


def mock_prank(payload: dict) -> dict:
    seed = seed_from_payload(payload)
    score = unit_float(seed, "score")
    reasons = []
    if payload.get("calls_24h", 0) > 3:
        reasons.append("high call frequency in 24h")
    if payload.get("coherence", 1.0) < 0.3:
        reasons.append("low transcript coherence")
    if payload.get("prior_prank_flags", 0) > 0:
        reasons.append("prior prank flags on this phone")
    return {
        "score": round(score, 2),
        "suspicious": score > 0.7 or bool(reasons),
        "reasons": reasons,
    }
