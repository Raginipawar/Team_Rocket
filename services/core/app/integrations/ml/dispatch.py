"""A's own capability (dispatch_rank) called from the dispatch round loop.
technical.md §9.6: on failure, fall back to nearest-first ranking (still
correct, just not optimal) instead of blocking dispatch."""

from .base import MLUnavailable, call_ml

DISPATCH_RANK_TIMEOUT_S = 5.0


async def dispatch_rank(emergency: dict, candidates: list[dict]) -> list[dict]:
    try:
        result = await call_ml(
            "POST", "/ml/v1/dispatch-rank", capability="dispatch_rank", timeout_s=DISPATCH_RANK_TIMEOUT_S,
            json={"emergency": emergency, "candidates": candidates},
        )
        return result["ranked"]
    except (MLUnavailable, KeyError):
        # Fallback: nearest-first, using distance_m already on each candidate.
        ranked = sorted(candidates, key=lambda c: c["distance_m"])
        return [
            {
                "ambulance_id": c["ambulance_id"], "accept_prob": 0.5,
                "expected_accept_latency_s": 10.0, "expected_arrival_sec": c["eta_sec"],
                "score": 1.0 / max(c["eta_sec"], 1),
            }
            for c in ranked
        ]
