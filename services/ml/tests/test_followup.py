import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.util.protocols import load_followup_tree
from app.capabilities.followup.mock import mock_followup_next, mock_followup_parse, MAX_QUESTIONS

FACILITIES = ["cardiac", "stroke", "trauma", "burns", "respiratory",
              "obstetric", "pediatric", "poisoning", "general"]


def test_every_facility_has_a_tree():
    for facility in FACILITIES:
        tree = load_followup_tree(facility)
        assert tree is not None, f"missing protocol file for {facility}"
        assert tree["facility"] == facility
        assert len(tree["questions"]) > 0


def test_selection_never_returns_unknown_id():
    tree = load_followup_tree("cardiac")
    valid_ids = {q["id"] for q in tree["questions"]}
    result = mock_followup_next({"facility": "cardiac", "acuity": "critical", "extracted": {}, "answers": [], "language": "en"})
    assert result["question"]["id"] in valid_ids


def test_stops_after_max_questions():
    answers = [{"question_id": f"c_{i}", "answer": "yes"} for i in range(MAX_QUESTIONS)]
    result = mock_followup_next({"facility": "cardiac", "acuity": "critical", "extracted": {}, "answers": answers, "language": "en"})
    assert result["done"] is True


def test_parse_yes_no():
    assert mock_followup_parse({"question_id": "x", "raw_answer": "yes", "language": "en"})["parsed"] is True
    assert mock_followup_parse({"question_id": "x", "raw_answer": "haan", "language": "hi"})["parsed"] is True
    assert mock_followup_parse({"question_id": "x", "raw_answer": "no", "language": "en"})["parsed"] is False


def test_parse_number():
    assert mock_followup_parse({"question_id": "x", "raw_answer": "42", "language": "en"})["parsed"] == 42
