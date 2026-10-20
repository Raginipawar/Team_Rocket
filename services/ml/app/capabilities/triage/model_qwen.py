"""Alternate triage engine: Qwen2.5-7B-Instruct via Ollama, same pattern
already proven in capabilities/extract/model.py (JSON-constrained decoding,
temperature 0, one repair retry). Built because the trained MuRIL model
(model.py) was fine-tuned on a small synthetic dataset and its real-world
accuracy is unverified -- a well-prompted general LLM that's already
running in this stack for extraction/follow-up/translation is a plausible
upgrade with zero new infrastructure.

Deliberately NOT the default. Selected only when TRIAGE_ENGINE=qwen (see
config.py, router.py) -- model.py's real_triage (MuRIL) stays the default
and completely untouched, so this is a one-line env var to try or revert,
never a replacement that has to be trusted blind. The rule-based safety
net (_fragility/_mlc_flag) is reused unchanged from model.py so neither
engine can weaken it -- it's the one thing that doesn't vary by engine."""

import json

import httpx

from app.config import get_settings
from .model import ACUITIES, FACILITIES, NEEDS_REVIEW_THRESHOLD, _fragility, _mlc_flag

TIMEOUT_S = 30.0

SYSTEM_PROMPT = f"""You are an emergency triage classifier. Given a caller's
transcript (and any already-extracted facts), classify two things:

1. acuity: one of {ACUITIES} -- "critical" means immediate life threat
   (unconscious, not breathing, severe bleeding, suspected stroke/MI,
   major trauma). "urgent" means needs care soon but not immediately
   life-threatening. "stable" means minor/non-emergency.
2. facility: one of {FACILITIES} -- the specialty care type most needed.

The transcript may be in English, Hindi, Marathi, or a romanized/code-mixed
combination -- read it phonetically if romanized, do not treat it as
English. When genuinely uncertain, prefer the more severe acuity -- a
false "urgent" wastes a review, a false "stable" on a real critical case
risks a life.

Output ONLY a JSON object: {{"acuity": "...", "acuity_confidence": 0.0-1.0,
"facility": "...", "facility_confidence": 0.0-1.0, "reasoning": "one short
sentence"}}."""


class ModelNotLoaded(RuntimeError):
    pass


async def _call_ollama(prompt: str) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        try:
            response = await client.post(f"{settings.ollama_url}/api/generate", json={
                "model": settings.llm_model,
                "system": SYSTEM_PROMPT,
                "prompt": prompt,
                "format": "json",
                "options": {"temperature": 0},
                "stream": False,
            })
            response.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ModelNotLoaded(f"Ollama not reachable: {exc}") from exc
    return json.loads(response.json()["response"])


def _build_prompt(payload: dict) -> str:
    parts = [f"Transcript: {payload['text']}"]
    if payload.get("extracted"):
        parts.append(f"Extracted facts: {json.dumps(payload['extracted'], default=str)}")
    if payload.get("profile_summary"):
        parts.append(f"Patient profile: {payload['profile_summary']}")
    if payload.get("followup_answers"):
        parts.append(f"Follow-up answers: {payload['followup_answers']}")
    return "\n".join(parts)


async def real_triage_qwen(payload: dict) -> dict:
    raw = await _call_ollama(_build_prompt(payload))

    acuity = raw.get("acuity") if raw.get("acuity") in ACUITIES else "urgent"  # unknown value: fail toward review, not toward "stable"
    facility = raw.get("facility") if raw.get("facility") in FACILITIES else "general"
    acuity_conf = float(raw.get("acuity_confidence", 0.5))
    facility_conf = float(raw.get("facility_confidence", 0.5))
    confidence = min(acuity_conf, facility_conf)

    extracted = payload.get("extracted", {})
    return {
        "acuity": acuity,
        # A single LLM call doesn't naturally produce a full probability
        # distribution the way the trained classifier's softmax does --
        # this approximates one from its own stated confidence rather than
        # fabricating precision it doesn't have.
        "acuity_probs": {a: (acuity_conf if a == acuity else (1 - acuity_conf) / 2) for a in ACUITIES},
        "facility": facility,
        "facility_probs": {f: (facility_conf if f == facility else (1 - facility_conf) / (len(FACILITIES) - 1)) for f in FACILITIES},
        "confidence": round(confidence, 4),
        "needs_review": confidence < NEEDS_REVIEW_THRESHOLD,
        "fragility": _fragility(extracted),
        "mlc_flag": _mlc_flag(extracted),
    }
