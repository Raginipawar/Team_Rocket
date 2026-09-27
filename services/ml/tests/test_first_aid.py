import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.util.protocols import load_all_first_aid
from app.capabilities.first_aid.mock import select_first_aid


def test_all_11_protocols_load():
    protocols = load_all_first_aid()
    assert len(protocols) == 11
    for p in protocols:
        assert set(p["steps"].keys()) == {"en", "hi", "mr"}
        assert set(p["donts"].keys()) == {"en", "hi", "mr"}


def test_not_breathing_always_gets_cpr_regardless_of_facility():
    for facility in ("cardiac", "trauma", "burns", "general"):
        result = select_first_aid({"facility": facility, "acuity": "critical", "extracted": {"breathing": "absent"}})
        assert result["protocol_id"] == "hands_only_cpr"


def test_choking_overrides_facility_default():
    result = select_first_aid({"facility": "general", "acuity": "urgent",
                                "extracted": {"breathing": "normal", "symptoms": ["choking"]}})
    assert result["protocol_id"] == "choking"


def test_severe_bleeding_selected():
    result = select_first_aid({"facility": "trauma", "acuity": "critical", "extracted": {"bleeding": "severe"}})
    assert result["protocol_id"] == "severe_bleeding"


def test_facility_default_used_when_no_override_rule_matches():
    result = select_first_aid({"facility": "stroke", "acuity": "urgent", "extracted": {"breathing": "normal"}})
    assert result["protocol_id"] == "stroke_signs_wait"


def test_unknown_facility_falls_back_to_generic_default():
    result = select_first_aid({"facility": "unknown_facility", "acuity": "stable", "extracted": {}})
    assert result["protocol_id"] == "generic_default"
