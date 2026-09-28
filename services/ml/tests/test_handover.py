import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.capabilities.handover.model import _quote_is_grounded, _source_text


def test_grounded_quote_found_verbatim():
    assert _quote_is_grounded("severe chest pain", "My father has severe chest pain and is sweating")


def test_ungrounded_quote_not_found():
    assert not _quote_is_grounded("history of stroke", "My father has severe chest pain and is sweating")


def test_empty_quote_never_grounded():
    assert not _quote_is_grounded("", "My father has severe chest pain")


def test_source_text_extracted_field_serializes_to_json():
    payload = {"extracted": {"symptoms": ["chest_pain"], "age": 60}}
    text = _source_text("extracted", payload)
    assert "chest_pain" in text and "60" in text


def test_source_text_unknown_field_returns_empty():
    assert _source_text("nonsense_field", {"transcript": "x"}) == ""
