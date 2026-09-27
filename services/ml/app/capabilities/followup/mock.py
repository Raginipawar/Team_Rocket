"""Deterministic fallback selection (technical.md §9.7: 'otherwise fall back
to the highest-priority unanswered question'). This is not a placeholder --
it's the documented safe path when the LLM is unavailable or returns an
unknown id, so it's also what runs under ML_MODE=mock."""

from app.util.protocols import load_followup_tree

MAX_QUESTIONS = 5


def _question_out(q: dict, language: str) -> dict:
    return {
        "id": q["id"],
        "text": q["text"].get(language, q["text"]["en"]),
        "answer_type": q["answer_type"],
        "choices": q.get("choices"),
        "audio_url": f"/ml/v1/static/audio/{q['audio'].get(language, q['audio']['en'])}",
    }


def pick_next_rule_based(payload: dict) -> dict:
    tree = load_followup_tree(payload["facility"]) or load_followup_tree("general")
    answered_ids = {a["question_id"] for a in payload.get("answers", [])}

    if len(answered_ids) >= MAX_QUESTIONS or tree is None:
        return {"done": True}

    candidates = [q for q in tree["questions"] if q["id"] not in answered_ids]
    if not candidates:
        return {"done": True}

    next_q = min(candidates, key=lambda q: q["priority"])
    return {"question": _question_out(next_q, payload.get("language", "en")), "done": False}


def mock_followup_next(payload: dict) -> dict:
    return pick_next_rule_based(payload)


def mock_followup_parse(payload: dict) -> dict:
    """Best-effort parse without an LLM: yes/no keyword match, else raw string."""
    raw = payload["raw_answer"].strip().lower()
    yes_words = {"yes", "haan", "han", "ha", "houy", "ho"}
    no_words = {"no", "nahi", "nahin", "nako", "naa"}
    if raw in yes_words:
        return {"parsed": True}
    if raw in no_words:
        return {"parsed": False}
    if raw.isdigit():
        return {"parsed": int(raw)}
    return {"parsed": payload["raw_answer"]}
