"""Real LightGBM LambdaRank hospital ranking (technical.md Section9.13).
Was a pure pass-through to the mock (sort-by-eta_sec only, explanation
always a single canned eta string) -- now a real trained model with real
per-prediction explanations via LightGBM's native pred_contrib."""

import asyncio

from app.capabilities.hospital_rank.model import rank_hospitals
from app.capabilities.hospital_rank.schemas import Candidate, Emergency, HospitalFeatures, HospitalRankRequest


def _candidate(hospital_id: str, **overrides) -> Candidate:
    defaults = dict(
        facility_match=True, required_resources_available_prob=0.8, p_bed_available_at_eta=0.8,
        eta_sec=600, eta_high_sec=800, road_comfort=80, specialist_on_duty_at_eta=0.8,
        staleness_min=5, occupancy_ratio=0.5, rejection_rate_24h=0.1, incoming_reserved_count=1,
        stabilization_capable=True, fragility="low",
    )
    defaults.update(overrides)
    return Candidate(hospital_id=hospital_id, features=HospitalFeatures(**defaults))


def test_facility_mismatch_ranks_below_a_matching_hospital():
    emergency = Emergency(acuity="critical", facility="cardiac", fragility="high", required_resources=["cardiologist"])
    good = _candidate("good", facility_match=True)
    mismatched = _candidate("mismatched", facility_match=False, required_resources_available_prob=0.3)
    req = HospitalRankRequest(emergency=emergency, candidates=[mismatched, good])

    results = asyncio.run(rank_hospitals(req))
    by_id = {r.hospital_id: r for r in results}
    assert by_id["good"].rank < by_id["mismatched"].rank
    assert by_id["good"].score > by_id["mismatched"].score


def test_explanation_is_real_not_a_single_canned_eta_string():
    emergency = Emergency(acuity="urgent", facility="general", fragility="low", required_resources=[])
    req = HospitalRankRequest(emergency=emergency, candidates=[_candidate("h1"), _candidate("h2", eta_sec=1500)])

    results = asyncio.run(rank_hospitals(req))
    for r in results:
        assert len(r.explanation) >= 1
        # the old mock's explanation was always exactly this one templated string
        assert not all(e.text.endswith("min ETA") for e in r.explanation) or len(r.explanation) > 1


def test_different_feature_profiles_produce_different_scores():
    emergency = Emergency(acuity="critical", facility="trauma", fragility="medium", required_resources=[])
    req = HospitalRankRequest(emergency=emergency, candidates=[
        _candidate("fresh", staleness_min=1, occupancy_ratio=0.2),
        _candidate("stale", staleness_min=80, occupancy_ratio=0.95),
    ])
    results = asyncio.run(rank_hospitals(req))
    scores = {r.hospital_id: r.score for r in results}
    assert scores["fresh"] != scores["stale"]
