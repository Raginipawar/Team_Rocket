"""T31 (technical.md Section14): family token must never receive clinical
fields. Also locks in the deny-lists for the other operational roles so a
future field added to Emergency doesn't silently become visible/invisible
to the wrong role without a test failing."""

import pytest

from app.domain.privacy import project

FULL_EMERGENCY = {
    "id": "e1", "status": "hospital_confirmed", "version": 3,
    "caller_user_id": "u1", "caller_phone": "+919999999999",
    "raw_text": "my father is having chest pain", "transcript": "my father is having chest pain",
    "language": "en", "stt_confidence": 0.92,
    "extracted": {"symptoms": ["chest_pain", "sweating"]},
    "lat": 18.5679, "lng": 73.9143, "location_accuracy_m": 10.0,
    "location_source": "gps", "landmark_text": None,
    "ai_acuity": "critical", "ai_facility": "cardiac", "ai_confidence": 0.9,
    "ai_probs": {"critical": 0.9, "urgent": 0.08, "stable": 0.02}, "needs_review": False,
    "final_acuity": "critical", "final_facility": "cardiac",
    "required_ambulance_type": "ALS", "fragility": True, "mlc_flag": False,
    "prank_score": 0.02, "prank_verified": False, "duplicate_of": None,
    "predicted_resources": {"cardiologist": 0.95}, "handover_note": {"summary": "..."},
    "ambulance_id": "a1", "hospital_id": "h1", "reservation_id": "r1",
    "eta_to_patient_sec": 300, "eta_to_hospital_sec": 900,
    "eta_low_sec": 250, "eta_high_sec": 1100, "escalated": False,
    "received_at": "2026-10-03T12:00:00Z", "triaged_at": "2026-10-03T12:01:00Z",
}

_CLINICAL_FIELDS = (
    "raw_text", "transcript", "extracted", "ai_acuity", "ai_facility", "ai_confidence",
    "ai_probs", "needs_review", "final_acuity", "final_facility", "required_ambulance_type",
    "fragility", "mlc_flag", "predicted_resources", "handover_note",
)


def test_family_never_receives_clinical_fields():
    projected = project("family", FULL_EMERGENCY)
    for field in _CLINICAL_FIELDS:
        assert field not in projected, f"T31 VIOLATION: family received clinical field '{field}'"


def test_family_never_receives_other_peoples_pii():
    projected = project("family", FULL_EMERGENCY)
    assert "caller_phone" not in projected
    assert "caller_user_id" not in projected


def test_family_still_gets_logistics_for_tracking():
    projected = project("family", FULL_EMERGENCY)
    for field in ("id", "status", "ambulance_id", "hospital_id", "eta_to_patient_sec", "eta_to_hospital_sec"):
        assert field in projected, f"family tracking needs '{field}' and it was stripped"


def test_patient_sees_own_clinical_data_but_not_internal_signals():
    projected = project("patient", FULL_EMERGENCY)
    assert projected["final_acuity"] == "critical"
    assert "prank_score" not in projected
    assert "duplicate_of" not in projected


def test_paramedic_sees_clinical_but_not_fraud_signals():
    projected = project("paramedic", FULL_EMERGENCY)
    assert projected["transcript"] == FULL_EMERGENCY["transcript"]
    assert projected["mlc_flag"] is False
    assert "prank_score" not in projected


def test_hospital_staff_sees_clinical_but_not_caller_pii():
    projected = project("hospital_staff", FULL_EMERGENCY)
    assert projected["final_facility"] == "cardiac"
    assert "caller_phone" not in projected
    assert "raw_text" not in projected


def test_developer_sees_everything_unfiltered():
    assert project("developer", FULL_EMERGENCY) == FULL_EMERGENCY


def test_unknown_role_rejected():
    with pytest.raises(ValueError):
        project("ops", FULL_EMERGENCY)  # "ops" is not a real DB role -- "developer" is
