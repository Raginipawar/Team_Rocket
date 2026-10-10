"""Simulated-episode utility labels for hospital ranking (UTILITY.md,
technical.md Section9.13). Was a partial generator -- only 4 of the real
13 features HospitalFeatures (app/capabilities/hospital_rank/schemas.py)
actually uses (eta_sec, p_bed_available, staleness_min, road_comfort),
missing facility_match/specialist/occupancy/rejection/incoming/
stabilization/fragility entirely, so a model trained on it couldn't use
the real feature set the serving code provides. Rewritten to the full
schema, same utility formula as UTILITY.md, same quantile relevance
grading, per-query hospital_id uniqueness fixed too (was f"h_{cid}" with
cid reused across every query -- all queries shared the same 10 hospital
ids, not a real per-episode candidate pool)."""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(7)
N_QUERIES = 10000
REROUTE_DELAY_SEC = 900
SPECIALIST_DELAY_SEC = 1800
FRAGILITY_COMFORT_MULTIPLIER = {"low": 2, "medium": 5, "high": 10}


def _simulate_candidate(qid: int, cid: int, fragility: str) -> dict:
    facility_match = RNG.random() < 0.7
    eta_sec = RNG.uniform(180, 2400)
    p_no_bed = RNG.uniform(0, 0.5)
    p_no_specialist = RNG.uniform(0, 0.4) if facility_match else RNG.uniform(0.3, 0.9)
    staleness_min = RNG.uniform(0, 90)
    road_comfort = RNG.uniform(30, 100)
    occupancy_ratio = RNG.uniform(0.2, 0.98)
    rejection_rate_24h = RNG.uniform(0, 0.5)
    incoming_reserved_count = RNG.integers(0, 8)
    stabilization_capable = RNG.random() < 0.6

    comfort_penalty = (100 - road_comfort) * FRAGILITY_COMFORT_MULTIPLIER[fragility]
    occupancy_penalty = occupancy_ratio * 300  # a near-full hospital adds real friction beyond bed probability alone
    rejection_penalty = rejection_rate_24h * 400  # hospitals that reject often cost real time even if "eligible"
    facility_mismatch_penalty = 0 if facility_match else 3000  # a near-hard constraint, not just a soft preference

    utility = (
        eta_sec + p_no_bed * REROUTE_DELAY_SEC + p_no_specialist * SPECIALIST_DELAY_SEC
        + staleness_min * 10 + comfort_penalty + occupancy_penalty + rejection_penalty + facility_mismatch_penalty
    )

    return {
        "query_id": qid, "hospital_id": f"q{qid}_h{cid}",
        "facility_match": int(facility_match),
        "required_resources_available_prob": round(1 - p_no_specialist, 4),
        "p_bed_available_at_eta": round(1 - p_no_bed, 4),
        "eta_sec": round(eta_sec, 1), "eta_high_sec": round(eta_sec * 1.3, 1),
        "road_comfort": round(road_comfort, 1),
        "specialist_on_duty_at_eta": round(1 - p_no_specialist, 4),
        "staleness_min": round(staleness_min, 1),
        "occupancy_ratio": round(occupancy_ratio, 4),
        "rejection_rate_24h": round(rejection_rate_24h, 4),
        "incoming_reserved_count": int(incoming_reserved_count),
        "stabilization_capable": int(stabilization_capable),
        "fragility_high": int(fragility == "high"),
        "fragility_medium": int(fragility == "medium"),
        "utility": utility,
    }


def main() -> None:
    rows = []
    for qid in range(N_QUERIES):
        fragility = RNG.choice(["low", "medium", "high"])
        n_candidates = RNG.integers(3, 11)
        candidates = [_simulate_candidate(qid, cid, fragility) for cid in range(n_candidates)]
        candidates.sort(key=lambda c: c["utility"])  # lower utility = better

        n = len(candidates)
        for i, c in enumerate(candidates):
            pct = i / n
            c["relevance"] = 4 if pct < 0.2 else 3 if pct < 0.4 else 2 if pct < 0.6 else 1 if pct < 0.8 else 0
            rows.append(c)

    df = pd.DataFrame(rows)
    df.to_csv("services/ml/data/hospital_rank/lambdarank_train.csv", index=False)
    print(f"wrote {len(df)} rows across {N_QUERIES} queries, "
          f"relevance distribution: {df['relevance'].value_counts().sort_index().to_dict()}")


if __name__ == "__main__":
    main()
