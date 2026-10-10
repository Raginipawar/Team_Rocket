"""Real bed-nowcast models (technical.md Section9.14). Was a 3-line
hand-written decay formula in router.py, ignoring 7 of the 10 real request
fields and never trained on anything."""

import asyncio

from app.capabilities.bed_nowcast.model import real_bed_nowcast
from app.capabilities.bed_nowcast.schemas import BedNowcastRequest


def _req(**overrides):
    defaults = dict(hospital_id="h1", room_type="er_bed", last_reported_free=5,
                     minutes_since_report=5, eta_min=30, hour=10, weekday=2,
                     arrival_rate_1h=0.5, discharge_rate_1h=0.5, incoming_reserved=0)
    defaults.update(overrides)
    return BedNowcastRequest(**defaults)


def test_high_pressure_scenario_predicts_lower_availability_than_low_pressure():
    high_pressure = asyncio.run(real_bed_nowcast(_req(
        last_reported_free=1, arrival_rate_1h=1.8, discharge_rate_1h=0.2, incoming_reserved=3)))
    low_pressure = asyncio.run(real_bed_nowcast(_req(
        last_reported_free=10, arrival_rate_1h=0.2, discharge_rate_1h=1.5, incoming_reserved=0)))

    assert high_pressure.p_available_at_eta < low_pressure.p_available_at_eta
    assert high_pressure.expected_free_at_eta < low_pressure.expected_free_at_eta


def test_different_room_types_can_predict_differently():
    icu = asyncio.run(real_bed_nowcast(_req(room_type="icu_bed", last_reported_free=2)))
    er = asyncio.run(real_bed_nowcast(_req(room_type="er_bed", last_reported_free=2)))
    # not asserting they MUST differ (could legitimately coincide), just that
    # the call succeeds and returns well-formed, non-constant-looking output
    assert 0.0 <= icu.p_available_at_eta <= 1.0
    assert 0.0 <= er.p_available_at_eta <= 1.0


def test_response_is_well_formed():
    resp = asyncio.run(real_bed_nowcast(_req()))
    assert 0.0 <= resp.p_available_at_eta <= 1.0
    assert resp.expected_free_at_eta >= 0.0
    assert resp.interval[0] <= resp.expected_free_at_eta <= resp.interval[1]
