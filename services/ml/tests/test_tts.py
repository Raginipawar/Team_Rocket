import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.capabilities.tts.mock import mock_tts


def test_mock_tts_is_deterministic_by_hash():
    a = mock_tts({"text": "hello", "language": "en"})
    b = mock_tts({"text": "hello", "language": "en"})
    c = mock_tts({"text": "hello", "language": "hi"})
    assert a["audio_url"] == b["audio_url"]
    assert a["audio_url"] != c["audio_url"]
