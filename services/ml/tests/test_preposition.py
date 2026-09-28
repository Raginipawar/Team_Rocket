"""Unit tests for coverage gain and the ALS constraint (technical.md §9.16:
'Unit tests for coverage gain and the ALS constraint')."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.capabilities.preposition.model import real_preposition

PUNE = (18.5204, 73.8567)


def offset(base, dx_km, dy_km):
    dlat = dy_km / 111.32
    dlng = dx_km / (111.32 * 0.9)
    return {"lat": base[0] + dlat, "lng": base[1] + dlng}


def test_coverage_gain_positive_when_ambulance_can_reach_high_demand_zone():
    # ALS here (not BLS): with only 2 candidate zones, "top quartile" is
    # degenerate and classifies the hot zone as high-demand, which requires
    # ALS coverage -- that constraint is tested on its own below. This test
    # is about coverage gain in isolation.
    payload = {
        "idle_ambulances": [{"id": "amb1", "location": offset(PUNE, 20, 0), "type": "ALS"}],
        "forecast": [
            {"h3_cell": "hot", **offset(PUNE, 22, 0), "predicted_calls": 8.0},
            {"h3_cell": "cold", **offset(PUNE, -20, 0), "predicted_calls": 0.5},
        ],
    }
    result = asyncio.run(real_preposition(payload))
    assert len(result["suggestions"]) == 1
    assert result["suggestions"][0]["h3_cell"] == "hot"
    assert result["suggestions"][0]["expected_coverage_gain"] > 0


def test_no_suggestion_when_nothing_reachable_within_8min():
    payload = {
        "idle_ambulances": [{"id": "amb1", "location": offset(PUNE, 0, 0), "type": "BLS"}],
        "forecast": [{"h3_cell": "far", **offset(PUNE, 200, 0), "predicted_calls": 10.0}],
    }
    result = asyncio.run(real_preposition(payload))
    assert result["suggestions"] == []


def test_high_demand_zone_requires_als_not_bls():
    """A high-demand zone reachable only by a BLS ambulance must NOT be
    claimed as covered -- the >=1-ALS-per-high-demand-zone constraint."""
    payload = {
        "idle_ambulances": [{"id": "bls1", "location": offset(PUNE, 1, 0), "type": "BLS"}],
        "forecast": [
            {"h3_cell": "hot", **offset(PUNE, 1.5, 0), "predicted_calls": 10.0},
            {"h3_cell": "cold1", **offset(PUNE, 1.6, 0), "predicted_calls": 0.1},
            {"h3_cell": "cold2", **offset(PUNE, 1.7, 0), "predicted_calls": 0.1},
            {"h3_cell": "cold3", **offset(PUNE, 1.8, 0), "predicted_calls": 0.1},
        ],
    }
    result = asyncio.run(real_preposition(payload))
    covered_cells = {s["h3_cell"] for s in result["suggestions"]}
    assert "hot" not in covered_cells  # BLS-only coverage of a high-demand zone is disallowed


def test_high_demand_zone_covered_when_als_available():
    payload = {
        "idle_ambulances": [
            {"id": "als1", "location": offset(PUNE, 1, 0), "type": "ALS"},
            {"id": "bls1", "location": offset(PUNE, 1, 0.5), "type": "BLS"},
        ],
        "forecast": [
            {"h3_cell": "hot", **offset(PUNE, 1.5, 0), "predicted_calls": 10.0},
            {"h3_cell": "cold1", **offset(PUNE, 1.6, 0), "predicted_calls": 0.1},
            {"h3_cell": "cold2", **offset(PUNE, 1.7, 0), "predicted_calls": 0.1},
            {"h3_cell": "cold3", **offset(PUNE, 1.8, 0), "predicted_calls": 0.1},
        ],
    }
    result = asyncio.run(real_preposition(payload))
    hot_suggestion = next((s for s in result["suggestions"] if s["h3_cell"] == "hot"), None)
    assert hot_suggestion is not None
    assert hot_suggestion["ambulance_id"] == "als1"
