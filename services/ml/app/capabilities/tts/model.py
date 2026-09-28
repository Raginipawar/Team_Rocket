"""Real TTS: AI4Bharat Indic Parler-TTS. Cached by sha256(text+lang) to a .wav
file under services/ml/artifacts/audio/, served at
/ml/v1/static/audio/{hash}.wav (technical.md §9.18). prerender.py (build step,
not yet implemented) renders every protocol question and first-aid step in
en/hi/mr at startup so the demo never waits on live synthesis."""

import hashlib
from pathlib import Path

AUDIO_DIR = Path("services/ml/artifacts/audio")


class ModelNotLoaded(RuntimeError):
    pass


def _cache_path(text: str, language: str) -> Path:
    h = hashlib.sha256(f"{text}:{language}".encode()).hexdigest()
    return AUDIO_DIR / f"{h}.wav"


async def real_tts(payload: dict) -> dict:
    path = _cache_path(payload["text"], payload["language"])
    if path.exists():
        return {"audio_url": f"/ml/v1/static/audio/{path.name}", "cached": True}

    raise ModelNotLoaded(
        "Indic Parler-TTS not loaded -- download AI4Bharat Indic Parler-TTS weights, "
        "or set ML_MOCK_CAPABILITIES=tts"
    )
