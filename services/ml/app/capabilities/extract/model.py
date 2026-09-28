"""Real extraction: Qwen2.5-7B-Instruct via Ollama, JSON-schema constrained
decoding (Ollama `format`), temperature 0, Pydantic validation with one
repair retry (technical.md §9.2)."""

import json

import httpx

from .schemas import ExtractedFacts

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2.5:7b-instruct"
TIMEOUT_S = 30.0

SYSTEM_PROMPT = """You extract structured facts from an emergency call transcript.
The transcript may be in English, Hindi (Devanagari or romanized/Hinglish
spelling, e.g. "seene mein dard" = chest pain), Marathi (Devanagari or
romanized), or a code-mixed combination. Romanized Hindi/Marathi text uses
Latin letters to spell out the same words phonetically -- read it phonetically
and translate the meaning, do not treat it as English. Only extract facts
that are actually stated or clearly implied by the transcript; never invent
symptoms, relations, or details absent from the text.

Fields:
- age: integer or null. age_confidence: "stated" (caller said the exact age), "estimated" (caller implied an age range), or "unknown".
- sex: "M", "F", or null.
- patient_count: integer, default 1.
- conscious: boolean or null.
- breathing: "normal", "difficult", "absent", or null.
- bleeding: "none", "mild", "severe", or null.
- symptoms: list of short lowercase snake_case symptom tags (e.g. "chest_pain", "breathlessness").
- mechanism: one of "none", "road_accident", "fall", "assault", "burn", "poisoning", "drowning", "other".
- pregnant: boolean, default false.
- landmark: a location/landmark string mentioned in the text, or null.
- for_whom: who the patient is relative to the caller (e.g. "self", "father", "mother", "stranger"), or null.
- coherence: float 0-1, how coherent/clear the transcript is.

Output ONLY a JSON object with exactly these fields. Do not invent facts not
present or implied in the text."""


class ModelNotLoaded(RuntimeError):
    pass


async def _call_ollama(text: str, language: str, repair_context: str | None = None) -> dict:
    prompt = f"Language: {language}\nTranscript: {text}"
    if repair_context:
        prompt += f"\n\nYour previous output was invalid: {repair_context}\nReturn corrected JSON only."

    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        try:
            response = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": MODEL,
                "system": SYSTEM_PROMPT,
                "prompt": prompt,
                "format": "json",
                "options": {"temperature": 0},
                "stream": False,
            })
            response.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ModelNotLoaded(f"Ollama not reachable at {OLLAMA_URL}: {exc}") from exc

    return json.loads(response.json()["response"])


async def real_extract(payload: dict) -> dict:
    text, language = payload["text"], payload["language"]

    raw = await _call_ollama(text, language)
    try:
        validated = ExtractedFacts.model_validate(raw)
        return validated.model_dump(exclude={"model_version", "latency_ms"})
    except Exception as exc:
        raw_repair = await _call_ollama(text, language, repair_context=str(exc))
        validated = ExtractedFacts.model_validate(raw_repair)  # let this raise if repair also fails
        return validated.model_dump(exclude={"model_version", "latency_ms"})
