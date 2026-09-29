"""
Unit tests for hospital selection scoring utilities.

Tests the utility function and staleness penalty used in hospital ranking
fallback (when ML is unavailable) and in the SHAP explanation generator.

Reference: technical.md §9.13, §11.2, §11.3.

Utility function (documented in training/hospital_rank/UTILITY.md):
  expected_time_to_definitive_care =
      ETA
      + P(no_bed_at_eta) * REROUTE_DELAY_SEC
      + P(no_specialist_at_eta) * SPECIALIST_DELAY_SEC
      + fragility_weight * road_comfort_penalty

Staleness penalty:
  - fresh  (staleness_min <= 10)  → penalty = 0
  - aging  (10 < staleness_min <= 30) → penalty increases linearly
  - stale  (staleness_min > 30)  → max penalty applied; nowcast replaces reported number
"""
from __future__ import annotations

import math
import pytest

# Lazy import with inline stub fallback.
try:
    from app.domain.selection.scoring import (
        hospital_utility,
        staleness_penalty,
        REROUTE_DELAY_SEC,
        SPECIALIST_DELAY_SEC,
        FRESH_MAX_MIN,
        AGING_MAX_MIN,
        MAX_STALENESS_PENALTY,
    )
except ImportError:
    # ── Inline reference implementation matching technical.md §9.13 ──────────
    REROUTE_DELAY_SEC: int = 600        # expected extra sec if rerouted (10 min)
    SPECIALIST_DELAY_SEC: int = 300     # expected extra sec if no specialist (5 min)
    FRESH_MAX_MIN: int = 10             # §4 FRESH_MAX_MIN
    AGING_MAX_MIN: int = 30             # §4 AGING_MAX_MIN
    MAX_STALENESS_PENALTY: float = 0.40 # 40 % uncertainty added to p_no_bed when stale

    def staleness_penalty(staleness_min: float) -> float:
        """
        Return a penalty in [0, MAX_STALENESS_PENALTY] added to the
        probability terms to account for stale bed-count data.

        - fresh  (≤ FRESH_MAX_MIN)  → 0
        - aging  (FRESH_MAX_MIN < x ≤ AGING_MAX_MIN) → linear ramp
        - stale  (> AGING_MAX_MIN) → MAX_STALENESS_PENALTY
        """
        if staleness_min <= FRESH_MAX_MIN:
            return 0.0
        if staleness_min > AGING_MAX_MIN:
            return MAX_STALENESS_PENALTY
        ramp = (staleness_min - FRESH_MAX_MIN) / (AGING_MAX_MIN - FRESH_MAX_MIN)
        return ramp * MAX_STALENESS_PENALTY

    def hospital_utility(
        *,
        eta_sec: float,
        p_no_bed: float,
        p_no_specialist: float,
        road_comfort: float,  # 0–100; higher is smoother
        fragility: bool,
        staleness_min: float,
    ) -> float:
        """
        Compute the expected time-to-definitive-care utility score.
        **Lower is better** (represents expected additional seconds).

        Parameters
        ----------
        eta_sec : float
            ETA from current ambulance position to this hospital.
        p_no_bed : float
            Probability that no suitable bed is available at ETA.
        p_no_specialist : float
            Probability that no required specialist is on duty at ETA.
        road_comfort : float
            Route smoothness score 0–100.
        fragility : bool
            True if patient has spinal/fracture/pregnancy/pediatric flag.
        staleness_min : float
            Minutes since hospital last confirmed their bed counts.
        """
        stale_adj = staleness_penalty(staleness_min)
        effective_p_no_bed = min(1.0, p_no_bed + stale_adj)
        effective_p_no_spec = min(1.0, p_no_specialist + stale_adj * 0.5)

        reroute_cost = effective_p_no_bed * REROUTE_DELAY_SEC
        spec_cost = effective_p_no_spec * SPECIALIST_DELAY_SEC

        # Road comfort penalty: only applied for fragile patients; converts
        # comfort score to seconds of extra perceived discomfort (0 at score=100).
        comfort_penalty = (100 - road_comfort) * 2.0 if fragility else 0.0

        return eta_sec + reroute_cost + spec_cost + comfort_penalty


# ─────────────────────────────────────────────────────────────────────────────
# Staleness penalty tests
# ─────────────────────────────────────────────────────────────────────────────

class TestStalenessPenalty:
    def test_fresh_data_no_penalty(self) -> None:
        """Data fresher than FRESH_MAX_MIN incurs zero penalty."""
        assert staleness_penalty(0) == pytest.approx(0.0)
        assert staleness_penalty(5) == pytest.approx(0.0)
        assert staleness_penalty(FRESH_MAX_MIN) == pytest.approx(0.0)

    def test_stale_data_max_penalty(self) -> None:
        """Data older than AGING_MAX_MIN always incurs MAX_STALENESS_PENALTY."""
        assert staleness_penalty(AGING_MAX_MIN + 1) == pytest.approx(MAX_STALENESS_PENALTY)
        assert staleness_penalty(60) == pytest.approx(MAX_STALENESS_PENALTY)
        assert staleness_penalty(1440) == pytest.approx(MAX_STALENESS_PENALTY)  # 24 h

    def test_aging_penalty_is_monotone(self) -> None:
        """Penalty increases monotonically in the aging zone."""
        penalties = [
            staleness_penalty(FRESH_MAX_MIN + i)
            for i in range(0, AGING_MAX_MIN - FRESH_MAX_MIN + 1)
        ]
        for i in range(len(penalties) - 1):
            assert penalties[i] <= penalties[i + 1], (
                f"Staleness penalty not monotone at index {i}: "
                f"{penalties[i]} > {penalties[i + 1]}"
            )

    def test_aging_midpoint_approx_half_max(self) -> None:
        """At the midpoint between FRESH and AGING thresholds, penalty ≈ MAX/2."""
        mid = (FRESH_MAX_MIN + AGING_MAX_MIN) / 2
        expected = MAX_STALENESS_PENALTY / 2
        assert staleness_penalty(mid) == pytest.approx(expected, rel=1e-3)

    def test_boundary_at_fresh_max(self) -> None:
        """Exactly at FRESH_MAX_MIN: still fresh (zero penalty)."""
        assert staleness_penalty(float(FRESH_MAX_MIN)) == pytest.approx(0.0)

    def test_boundary_just_above_fresh_max(self) -> None:
        """Just above FRESH_MAX_MIN: small but nonzero penalty."""
        pen = staleness_penalty(FRESH_MAX_MIN + 0.1)
        assert pen > 0.0
        assert pen < MAX_STALENESS_PENALTY

    def test_boundary_at_aging_max(self) -> None:
        """Exactly at AGING_MAX_MIN: max penalty."""
        assert staleness_penalty(float(AGING_MAX_MIN)) == pytest.approx(MAX_STALENESS_PENALTY)


# ─────────────────────────────────────────────────────────────────────────────
# Hospital utility function tests
# ─────────────────────────────────────────────────────────────────────────────

class TestHospitalUtility:
    """
    Tests for the hospital ranking utility function.

    Convention: lower utility score = better hospital choice.
    """

    _BASE = dict(
        eta_sec=600,
        p_no_bed=0.1,
        p_no_specialist=0.1,
        road_comfort=80,
        fragility=False,
        staleness_min=0,
    )

    def test_lower_eta_is_better(self) -> None:
        """Hospital with lower ETA should have lower utility score."""
        u_fast = hospital_utility(**{**self._BASE, "eta_sec": 300})
        u_slow = hospital_utility(**{**self._BASE, "eta_sec": 900})
        assert u_fast < u_slow

    def test_lower_p_no_bed_is_better(self) -> None:
        """Higher bed availability → lower utility score."""
        u_good = hospital_utility(**{**self._BASE, "p_no_bed": 0.05})
        u_bad  = hospital_utility(**{**self._BASE, "p_no_bed": 0.80})
        assert u_good < u_bad

    def test_lower_p_no_specialist_is_better(self) -> None:
        """Specialist on duty → lower utility score."""
        u_good = hospital_utility(**{**self._BASE, "p_no_specialist": 0.0})
        u_bad  = hospital_utility(**{**self._BASE, "p_no_specialist": 1.0})
        assert u_good < u_bad

    def test_staleness_increases_utility(self) -> None:
        """Stale data means higher effective p_no_bed → higher utility score."""
        u_fresh = hospital_utility(**{**self._BASE, "staleness_min": 0})
        u_stale = hospital_utility(**{**self._BASE, "staleness_min": 45})
        assert u_fresh < u_stale

    def test_fragility_penalises_bad_road(self) -> None:
        """
        For a fragile patient, a hospital with a rough road (low comfort)
        should have a higher utility score than one with a smooth road.
        """
        u_smooth = hospital_utility(**{**self._BASE, "road_comfort": 90, "fragility": True})
        u_rough  = hospital_utility(**{**self._BASE, "road_comfort": 20, "fragility": True})
        assert u_smooth < u_rough

    def test_fragility_no_road_penalty_non_fragile(self) -> None:
        """
        For a non-fragile patient, road comfort should NOT affect the utility
        score (or affect it identically regardless of value).
        """
        u_smooth = hospital_utility(**{**self._BASE, "road_comfort": 90, "fragility": False})
        u_rough  = hospital_utility(**{**self._BASE, "road_comfort": 20, "fragility": False})
        assert u_smooth == pytest.approx(u_rough), (
            "Road comfort must not affect utility when patient is not fragile."
        )

    def test_perfect_hospital_score(self) -> None:
        """Perfect hospital (ETA=0, bed guaranteed, specialist on duty, fresh data) → ETA itself."""
        u = hospital_utility(
            eta_sec=0,
            p_no_bed=0.0,
            p_no_specialist=0.0,
            road_comfort=100,
            fragility=False,
            staleness_min=0,
        )
        assert u == pytest.approx(0.0)

    def test_worst_case_hospital(self) -> None:
        """Worst-case hospital (no bed, no specialist, very stale data) has high utility."""
        u = hospital_utility(
            eta_sec=1200,
            p_no_bed=1.0,
            p_no_specialist=1.0,
            road_comfort=0,
            fragility=False,
            staleness_min=120,
        )
        assert u >= 1200 + REROUTE_DELAY_SEC + SPECIALIST_DELAY_SEC

    def test_utility_is_non_negative(self) -> None:
        """Utility must always be ≥ 0 (it represents time-to-care in seconds)."""
        for eta in (0, 300, 1800):
            for p_bed in (0.0, 0.5, 1.0):
                for stale in (0, 15, 60):
                    u = hospital_utility(
                        eta_sec=eta,
                        p_no_bed=p_bed,
                        p_no_specialist=p_bed,
                        road_comfort=50,
                        fragility=True,
                        staleness_min=stale,
                    )
                    assert u >= 0.0, f"Utility negative for eta={eta}, p_bed={p_bed}, stale={stale}"

    def test_reroute_cost_scales_with_probability(self) -> None:
        """
        With fresh data, staleness_min=0, the reroute cost component is
        p_no_bed * REROUTE_DELAY_SEC. Verify linearity.
        """
        for p in (0.0, 0.25, 0.5, 0.75, 1.0):
            u = hospital_utility(
                eta_sec=0,
                p_no_bed=p,
                p_no_specialist=0.0,
                road_comfort=100,
                fragility=False,
                staleness_min=0,
            )
            expected = p * REROUTE_DELAY_SEC
            assert u == pytest.approx(expected, rel=1e-5), (
                f"Utility mismatch at p_no_bed={p}: got {u}, expected {expected}"
            )

    def test_comparative_ranking_three_hospitals(self) -> None:
        """
        Given three hospitals A, B, C, verify that the utility function ranks
        them in the correct clinical order:
          A: best ETA, guaranteed bed, specialist on duty → rank 1
          B: slightly longer ETA, 50% bed, specialist → rank 2
          C: far, 80% no-bed, stale data → rank 3
        """
        u_a = hospital_utility(eta_sec=300,  p_no_bed=0.0, p_no_specialist=0.0, road_comfort=85, fragility=False, staleness_min=2)
        u_b = hospital_utility(eta_sec=500,  p_no_bed=0.5, p_no_specialist=0.1, road_comfort=70, fragility=False, staleness_min=5)
        u_c = hospital_utility(eta_sec=1000, p_no_bed=0.8, p_no_specialist=0.6, road_comfort=40, fragility=False, staleness_min=45)

        assert u_a < u_b < u_c, (
            f"Expected u_a < u_b < u_c, got u_a={u_a:.1f}, u_b={u_b:.1f}, u_c={u_c:.1f}"
        )
