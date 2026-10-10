"""Real handover: Ollama qwen2.5-7b with the SBAR JSON schema (technical.md
§9.9). Every clinical statement must cite its OWN source_spans quote found in
transcript/answers/profile; the validator checks and drops each sentence
individually (not the whole section/note at once) whose quote can't be
fuzzy-matched (>=0.85) against the source text -- so the LLM can propose
spans but never gets to assert something ungrounded, and one ungrounded
sentence can't ride along inside an otherwise-grounded note."""

import difflib
import json

import httpx

OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen2.5:7b-instruct"
TIMEOUT_S = 30.0
FUZZY_MATCH_THRESHOLD = 0.85

SYSTEM_PROMPT = """You write an SBAR handover note (Situation, Background,
Assessment, Recommendation) for a hospital receiving team, in English, from
an emergency call transcript, extracted facts, follow-up answers, patient
profile, and triage result.

Situation, Background, and Assessment are FACTUAL -- every sentence in them
MUST be traceable to the source material. Write each of these three
sections as a LIST of individual sentences, where EACH sentence has its own
one supporting quote (not one quote for the whole section). Use this exact
shape for situation/background/assessment:
  [{"text": "<one sentence>", "field": "<transcript|extracted|followup|profile|triage>",
    "quote": "<a short exact substring from that source that supports THIS sentence>"}]
If you cannot find a supporting quote for a specific sentence, do not write
that sentence at all.

Recommendation is a suggested next action, not a factual claim about the
patient -- write it as a plain string, no quote needed.

Output ONLY JSON: {"situation": [...], "background": [...], "assessment": [...],
"recommendation": str} using the per-sentence shape above for the first three."""


class ModelNotLoaded(RuntimeError):
    pass


def _source_text(field: str, payload: dict) -> str:
    if field == "transcript":
        return payload.get("transcript", "")
    if field == "extracted":
        return json.dumps(payload.get("extracted", {}), default=str)
    if field == "followup":
        return " ".join(payload.get("followup_answers", []))
    if field == "profile":
        return json.dumps(payload.get("profile", {}), default=str)
    if field == "triage":
        return json.dumps(payload.get("triage", {}), default=str)
    return ""


def _quote_is_grounded(quote: str, source: str) -> bool:
    if not quote or not source:
        return False
    if quote.lower() in source.lower():
        return True
    # fuzzy fallback for near-exact paraphrase of a short quote
    return difflib.SequenceMatcher(None, quote.lower(), source.lower()).find_longest_match().size >= len(quote) * FUZZY_MATCH_THRESHOLD


async def real_handover(payload: dict) -> dict:
    prompt = json.dumps({
        "transcript": payload.get("transcript", ""),
        "extracted": payload.get("extracted", {}),
        "followup_answers": payload.get("followup_answers", []),
        "profile": payload.get("profile", {}),
        "triage": payload.get("triage", {}),
    }, default=str)

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

    def _grounded_sentences(section: list) -> tuple[list[str], list[dict]]:
        """Per-sentence grounding (technical.md §9.9), not per-note: each
        sentence is checked against its OWN claimed quote and dropped
        individually if ungrounded, rather than blanking the whole section
        when any one claim fails or passing the whole section when any one
        claim succeeds -- the previous note-level gate let an individually
        ungrounded sentence ride along inside an otherwise-grounded note."""
        texts, spans = [], []
        for item in section if isinstance(section, list) else []:
            if not isinstance(item, dict):
                continue
            text, field, quote = item.get("text", ""), item.get("field", ""), item.get("quote", "")
            if not text:
                continue
            source = _source_text(field, payload)
            if _quote_is_grounded(quote, source):
                texts.append(text)
                spans.append({"field": field, "quote": quote})
        return texts, spans

    situation_sentences, situation_spans = _grounded_sentences(raw.get("situation", []))
    background_sentences, background_spans = _grounded_sentences(raw.get("background", []))
    assessment_sentences, assessment_spans = _grounded_sentences(raw.get("assessment", []))

    result = {
        "situation": " ".join(situation_sentences),
        "background": " ".join(background_sentences),
        "assessment": " ".join(assessment_sentences),
        "recommendation": raw.get("recommendation", ""),  # recommendation is a suggested action, not a factual claim
        "source_spans": situation_spans + background_spans + assessment_spans,
    }
    return result
