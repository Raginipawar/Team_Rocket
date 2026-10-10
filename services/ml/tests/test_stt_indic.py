"""Real dual-model STT routing for Hindi/Marathi (technical.md Section9.1).
Generates real speech via gTTS (requires internet) and verifies the Indic
model actually gets used and produces a sensible transcript -- skipped
cleanly if gTTS/network isn't available rather than failing the suite."""

import asyncio

import pytest

gtts = pytest.importorskip("gtts", reason="gTTS not installed")

from app.capabilities.stt.model import real_stt


def _generate_clip(tmp_path, text: str, lang: str) -> bytes:
    path = tmp_path / f"{lang}.mp3"
    try:
        gtts.gTTS(text=text, lang=lang).save(str(path))
    except Exception as exc:
        pytest.skip(f"gTTS network call failed: {exc}")
    return path.read_bytes()


@pytest.mark.parametrize("lang,text", [
    ("hi", "मेरे पिता को सीने में दर्द हो रहा है और पसीना आ रहा है"),
    ("mr", "माझ्या वडिलांना छातीत दुखत आहे आणि घाम येत आहे"),
])
def test_indic_dual_model_routing_produces_real_transcript(tmp_path, lang, text):
    audio_bytes = _generate_clip(tmp_path, text, lang)
    result = asyncio.run(real_stt(audio_bytes, lang_hint=lang))

    assert result["transcript"], "transcript must not be empty"
    assert result["language"] == lang
    assert result["confidence"] > 0.5
    # Loose check -- ASR output won't be byte-identical to the TTS input,
    # but a working model should recover most of the Devanagari content.
    overlap = len(set(result["transcript"]) & set(text)) / len(set(text))
    assert overlap > 0.5, f"transcript barely resembles input: {result['transcript']!r}"
