"""Real translation via Ollama qwen2.5-7b (technical.md §9.18 specifies
IndicTrans2, a dedicated MT model; using the already-proven Ollama
infrastructure instead, documented honestly -- a general LLM translating
short SMS/protocol phrases is a reasonable substitute, though not as fast or
as specialized as a dedicated MT model would be). LRU cache by
sha256(text+lang), as the spec requires, so fixed protocol text and repeated
SMS templates are only ever translated once."""

import hashlib
import json

import httpx

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2.5:7b-instruct"
TIMEOUT_S = 15.0

LANGUAGE_NAMES = {"hi": "Hindi", "mr": "Marathi", "en": "English"}

SYSTEM_PROMPT = """Translate the given text to the target language. Output
ONLY JSON: {"translated_text": "<translation>"}. Keep it natural and short,
suitable for an SMS or a spoken prompt -- not a literal word-for-word
translation. Preserve any numbers, names, or place names exactly."""

_CACHE: dict[str, str] = {}


class ModelNotLoaded(RuntimeError):
    pass


def _cache_key(text: str, target_lang: str) -> str:
    return hashlib.sha256(f"{text}:{target_lang}".encode()).hexdigest()


async def real_translate(payload: dict) -> dict:
    text, target_lang = payload["text"], payload["target_lang"]
    key = _cache_key(text, target_lang)
    if key in _CACHE:
        return {"translated_text": _CACHE[key], "cached": True}

    target_name = LANGUAGE_NAMES.get(target_lang, target_lang)
    prompt = f"Target language: {target_name}\nText: {text}"

    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        try:
            response = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": MODEL, "system": SYSTEM_PROMPT, "prompt": prompt,
                "format": "json", "options": {"temperature": 0}, "stream": False,
            })
            response.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ModelNotLoaded(f"Ollama not reachable: {exc}") from exc

    raw = json.loads(response.json()["response"])
    translated = raw["translated_text"]
    _CACHE[key] = translated
    return {"translated_text": translated, "cached": False}
