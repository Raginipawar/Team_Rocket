import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.capabilities.handover.model import _quote_is_grounded, _source_text, real_handover


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


def test_ungrounded_sentence_dropped_individually_not_whole_note():
    """technical.md §9.9's actual requirement: per-sentence grounding, not
    per-note. A note with one grounded and one fabricated/ungrounded
    sentence must keep the grounded one and drop only the fabricated one --
    not blank the whole section and not let the fabrication ride along."""
    fake_raw = {
        "situation": [
            {"text": "Patient has chest pain.", "field": "transcript", "quote": "severe chest pain"},
            {"text": "Patient has a known history of three prior heart attacks.",
             "field": "transcript", "quote": "three prior heart attacks"},  # fabricated -- not in the transcript
        ],
        "background": [],
        "assessment": [],
        "recommendation": "Treat as cardiac emergency.",
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": json.dumps(fake_raw)}

    async def run():
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=FakeResponse()):
            payload = {"transcript": "My father has severe chest pain right now.",
                       "extracted": {}, "followup_answers": [], "profile": {}, "triage": {}}
            return await real_handover(payload)

    result = asyncio.run(run())
    assert "chest pain" in result["situation"]
    assert "three prior heart attacks" not in result["situation"]
    assert len(result["source_spans"]) == 1
