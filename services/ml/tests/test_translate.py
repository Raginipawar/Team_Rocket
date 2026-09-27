import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.capabilities.translate.mock import mock_translate


def test_mock_translate_tags_target_language():
    result = mock_translate({"text": "hello", "source_lang": "en", "target_lang": "mr"})
    assert "hello" in result["translated_text"]
    assert result["cached"] is False
