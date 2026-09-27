"""Real selection: Ollama qwen2.5-7b, temperature 0, receives current facts +
answered ids + candidate questions (id + English text) and returns
{question_id}. The LLM never writes question text (technical.md §9.7); if it
returns an unknown id, the caller falls back to mock.pick_next_rule_based."""

import json

import httpx

from app.util.protocols import load_followup_tree

from .mock import pick_next_rule_based

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2.5:7b-instruct"
TIMEOUT_S = 15.0

SELECT_SYSTEM_PROMPT = """You are choosing which follow-up question to ask
next in an emergency call, to reduce uncertainty about triage as fast as
possible. You will be given the current known facts, the ids of questions
already answered, and a list of candidate questions (id + English text).
Pick the ONE candidate question id whose answer would most reduce
uncertainty about the patient's acuity/facility given what's already known.
You must return one of the given candidate ids exactly -- never invent your
own question text. Output ONLY JSON: {"question_id": "<id>"}."""

PARSE_SYSTEM_PROMPT = """You map a free-text answer (possibly in Hindi,
Marathi, English, or code-mixed, romanized or native script) to a
structured value for one question. answer_type tells you the expected
shape: "yes_no" -> true/false, "number" -> an integer, "choice" -> one of
the given choices exactly, "free" -> the answer as a short string. Output
ONLY JSON: {"parsed": <value>}."""


class ModelNotLoaded(RuntimeError):
    pass


async def _ollama_json(system: str, prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        try:
            response = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": MODEL, "system": system, "prompt": prompt,
                "format": "json", "options": {"temperature": 0}, "stream": False,
            })
            response.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ModelNotLoaded(f"Ollama not reachable: {exc}") from exc
    return json.loads(response.json()["response"])


async def real_followup_next(payload: dict) -> dict:
    tree = load_followup_tree(payload["facility"]) or load_followup_tree("general")
    answered_ids = {a["question_id"] for a in payload.get("answers", [])}
    candidates = [q for q in tree["questions"] if q["id"] not in answered_ids]

    if len(answered_ids) >= 5 or not candidates:
        return {"done": True}

    prompt = json.dumps({
        "known_facts": payload.get("extracted", {}),
        "answered": [a["question_id"] for a in payload.get("answers", [])],
        "candidates": [{"id": q["id"], "text": q["text"]["en"]} for q in candidates],
    })
    raw = await _ollama_json(SELECT_SYSTEM_PROMPT, prompt)

    chosen_id = raw.get("question_id")
    valid_ids = {q["id"] for q in candidates}
    if chosen_id not in valid_ids:
        return pick_next_rule_based(payload)  # unknown id -> documented fallback, not an error

    chosen = next(q for q in candidates if q["id"] == chosen_id)
    language = payload.get("language", "en")
    return {
        "question": {
            "id": chosen["id"], "text": chosen["text"].get(language, chosen["text"]["en"]),
            "answer_type": chosen["answer_type"], "choices": chosen.get("choices"),
            "audio_url": f"/ml/v1/static/audio/{chosen['audio'].get(language, chosen['audio']['en'])}",
        },
        "done": False,
    }


FACILITIES = ["cardiac", "stroke", "trauma", "burns", "respiratory",
              "obstetric", "pediatric", "poisoning", "general"]


def _find_question(question_id: str) -> dict | None:
    for facility in FACILITIES:
        tree = load_followup_tree(facility)
        if tree is None:
            continue
        for q in tree["questions"]:
            if q["id"] == question_id:
                return q
    return None


async def real_followup_parse(payload: dict) -> dict:
    question = _find_question(payload["question_id"])
    prompt = json.dumps({
        "question_id": payload["question_id"], "raw_answer": payload["raw_answer"],
        "language": payload.get("language", "en"),
        "answer_type": question["answer_type"] if question else "free",
        "choices": question.get("choices") if question else None,
    })
    raw = await _ollama_json(PARSE_SYSTEM_PROMPT, prompt)
    return {"parsed": raw.get("parsed")}
