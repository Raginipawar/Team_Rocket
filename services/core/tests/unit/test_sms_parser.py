import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.integrations.sms.parser import (
    FollowupAnswer, NewEmergency, ParamedicCommand, PrankVerification, parse_inbound,
)


def test_paramedic_command_parsed():
    result = parse_inbound("GH 7b0c ARRIVED", open_followup=None)
    assert isinstance(result, ParamedicCommand)
    assert result.emergency_short_id == "7b0c"
    assert result.command == "ARRIVED"


def test_paramedic_command_case_insensitive():
    result = parse_inbound("gh 7b0c critical", open_followup=None)
    assert isinstance(result, ParamedicCommand)
    assert result.command == "CRITICAL"


def test_yes_is_prank_verification():
    result = parse_inbound("YES", open_followup=None)
    assert isinstance(result, PrankVerification)


def test_yes_lowercase_and_whitespace():
    result = parse_inbound("  yes  ", open_followup=None)
    assert isinstance(result, PrankVerification)


def test_followup_answer_when_open_question_exists():
    result = parse_inbound("no he is not breathing", open_followup={"emergency_id": "e1", "question_id": "q1"})
    assert isinstance(result, FollowupAnswer)
    assert result.emergency_id == "e1"
    assert result.question_id == "q1"


def test_new_emergency_when_no_open_question_and_no_keyword():
    result = parse_inbound("my father has chest pain please help", open_followup=None)
    assert isinstance(result, NewEmergency)


def test_paramedic_command_takes_priority_over_open_followup():
    """Priority order in technical.md §12.1: GH command is checked FIRST,
    even if the phone has an open follow-up question."""
    result = parse_inbound("GH 7b0c ONBOARD", open_followup={"emergency_id": "e1", "question_id": "q1"})
    assert isinstance(result, ParamedicCommand)


def test_yes_takes_priority_over_open_followup():
    result = parse_inbound("YES", open_followup={"emergency_id": "e1", "question_id": "q1"})
    assert isinstance(result, PrankVerification)
