from app.util.mock import seed_from_payload, unit_float


def mock_dispatch_rank(payload: dict) -> dict:
    seed = seed_from_payload(payload)
    ranked = []
    for i, c in enumerate(payload.get("candidates", [])):
        accept_prob = round(0.3 + unit_float(seed, f"p{i}") * 0.65, 2)
        latency_s = round(3 + unit_float(seed, f"l{i}") * 15, 1)
        score = round(accept_prob / (c["eta_sec"] + latency_s), 6)
        ranked.append({
            "ambulance_id": c["ambulance_id"],
            "accept_prob": accept_prob,
            "expected_accept_latency_s": latency_s,
            "expected_arrival_sec": c["eta_sec"],
            "score": score,
        })
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return {"ranked": ranked}
