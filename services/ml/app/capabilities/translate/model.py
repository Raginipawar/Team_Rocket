"""Real translation: AI4Bharat IndicTrans2 (en<->hi, en<->mr). LRU cache by
sha256(text+lang) (technical.md §9.18) so fixed protocol text and repeated SMS
templates are translated once. Fixed texts are pre-translated at build time
(services/ml/app/capabilities/tts/prerender.py will drive that once TTS is wired)."""

import hashlib

_CACHE: dict[str, str] = {}


class ModelNotLoaded(RuntimeError):
    pass


def _cache_key(text: str, target_lang: str) -> str:
    return hashlib.sha256(f"{text}:{target_lang}".encode()).hexdigest()


async def real_translate(payload: dict) -> dict:
    key = _cache_key(payload["text"], payload["target_lang"])
    if key in _CACHE:
        return {"translated_text": _CACHE[key], "cached": True}

    raise ModelNotLoaded(
        "IndicTrans2 not loaded -- download AI4Bharat IndicTrans2 weights, "
        "or set ML_MOCK_CAPABILITIES=translate"
    )
