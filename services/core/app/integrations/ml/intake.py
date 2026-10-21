"""Typed wrappers for the ML capabilities the intake pipeline calls (A's
domain: technical.md §9.1-9.6, §9.9-9.10). Timeouts and fallback behaviour are
copied verbatim from the spec -- the caller (domain/intake.py) decides what to
do with a fallback result, this module only knows how to reach ML and what
"unavailable" means per capability."""

from .base import MLUnavailable, call_ml

# The spec's timeouts assumed either mock-mode (near-instant) or a GPU-backed
# real deployment. On this machine's real models (Whisper STT, MuRIL-based
# extract/triage) running on CPU, with several capabilities firing
# concurrently in process_emergency's own asyncio.gather and contending for
# the same CPU, measured solo latency alone was STT ~14.5s and extract
# ~7.7s -- both well past the old 8s/6s timeouts. Every real SOS was silently
# hitting MLUnavailable and falling back to the fixed "critical/general/
# confidence 0.0" default, which is indistinguishable from the AI never
# having run at all. Raised with real margin for concurrent CPU-bound
# inference, not just the solo-call numbers.
STT_TIMEOUT_S = 30.0
# Was 20.0 -- shorter than extract/model.py's OWN internal Ollama timeout
# (30.0s), so this core-side call could time out and fall back before the ML
# service even finished its own real attempt + fallback. A capability's
# core-side timeout must always have margin beyond whatever the ML service
# itself waits internally, not just beyond the solo-call latency.
EXTRACT_TIMEOUT_S = 40.0
# Was 15.0 -- fine for the MuRIL engine (a dedicated small model, no Ollama
# contention), but triage now also runs through Ollama when TRIAGE_ENGINE=qwen,
# concurrently with duplicate-check in process_emergency's own asyncio.gather,
# right after extract() just used the same single-threaded Ollama queue. Same
# margin-beyond-the-ML-service's-own-timeout reasoning as EXTRACT_TIMEOUT_S/
# HANDOVER_TIMEOUT_S above -- found by a real SOS silently hitting
# MLUnavailable and falling back to critical/general/confidence-0.0, not by
# reading the code.
TRIAGE_TIMEOUT_S = 40.0
PRANK_TIMEOUT_S = 10.0
DUPLICATE_TIMEOUT_S = 10.0
RESOURCES_TIMEOUT_S = 10.0
# Same mismatch as EXTRACT_TIMEOUT_S above: was 15.0, shorter than
# handover/model.py's own internal Ollama timeout (30.0s).
HANDOVER_TIMEOUT_S = 40.0
# Needs margin beyond followup/model.py's own internal Ollama timeout
# (bumped to 30.0s there for the same CPU-inference-is-slow reason) plus the
# rule-based-mock fallback overhead, or this call times out and silently
# drops a real question as "done" before the ML side even finishes.
FOLLOWUP_TIMEOUT_S = 40.0
FIRST_AID_TIMEOUT_S = 5.0


async def stt(audio_bytes: bytes, filename: str, lang_hint: str | None = None) -> dict | None:
    """technical.md §9.1: on failure, emergency still created; dispatch proceeds
    as app_button (location + profile) with ALS; transcript retried in background."""
    try:
        return await call_ml(
            "POST", "/ml/v1/stt", capability="stt", timeout_s=STT_TIMEOUT_S,
            files={"audio": (filename, audio_bytes)},
            data={"lang_hint": lang_hint} if lang_hint else None,
        )
    except MLUnavailable:
        return None


async def extract(text: str, language: str) -> dict | None:
    """technical.md §9.2: on failure, triage runs on raw text only."""
    try:
        return await call_ml(
            "POST", "/ml/v1/extract", capability="extract", timeout_s=EXTRACT_TIMEOUT_S,
            json={"text": text, "language": language},
        )
    except MLUnavailable:
        return None


_ACUITY_RANK = {"stable": 0, "urgent": 1, "critical": 2}

# The real triage model (training/triage/model.py) is honest about being
# undertrained -- 258 synthetic samples, 0.15 critical_recall on its own
# eval. A caller literally saying "heart attack" and getting back
# urgent/general is that documented weakness, not a bug in this code. Real
# fix is retraining with real data; this is the pragmatic stopgap: a
# keyword safety net that can only ESCALATE the model's guess (never
# downgrade it), same "safe-side default" philosophy as the
# MLUnavailable fallback below.
_ESCALATION_KEYWORDS: list[tuple[str, str, str]] = [
    ("heart attack", "critical", "cardiac"),
    ("cardiac arrest", "critical", "cardiac"),
    ("chest pain", "critical", "cardiac"),
    ("not breathing", "critical", "respiratory"),
    ("can't breathe", "critical", "respiratory"),
    ("cannot breathe", "critical", "respiratory"),
    ("choking", "critical", "respiratory"),
    ("unconscious", "critical", "general"),
    ("unresponsive", "critical", "general"),
    ("stroke", "critical", "stroke"),
    ("face drooping", "critical", "stroke"),
    ("slurred speech", "critical", "stroke"),
    ("severe bleeding", "critical", "trauma"),
    ("bleeding heavily", "critical", "trauma"),
    ("seizure", "urgent", "general"),
]


def _apply_keyword_escalation(result: dict, text: str) -> dict:
    low = text.lower()
    for keyword, acuity, facility in _ESCALATION_KEYWORDS:
        if keyword in low and _ACUITY_RANK.get(acuity, 0) > _ACUITY_RANK.get(result.get("acuity"), 0):
            # The displayed confidence was still the undertrained model's own
            # raw softmax (e.g. 11%) even once a keyword match had already
            # overridden its acuity/facility guess -- confusing on its face:
            # a caller says "heart attack" and the UI shows critical/cardiac
            # at "11% sure". A keyword match is a certain, deterministic
            # determination, not a statistical guess, so its confidence
            # should say so. Only raises confidence, never lowers a model
            # that was already more confident on its own.
            result = {**result, "acuity": acuity, "facility": facility, "needs_review": True,
                      "confidence": max(result.get("confidence") or 0, 0.9),
                      "model_version": f"{result.get('model_version', 'model')}+keyword_escalation:{keyword}"}
    return result


async def triage(text: str, extracted: dict, profile_summary: str | None = None,
                  followup_answers: list[str] | None = None) -> dict:
    """technical.md §9.3: on failure, safe-side default -- acuity critical,
    facility general, needs_review=true (forces ALS dispatch). Never returns
    None: callers rely on this dict always having acuity/facility/needs_review."""
    payload = {
        "text": text, "extracted": extracted,
        "profile_summary": profile_summary,
        "followup_answers": followup_answers or [],
    }
    # The first attempt most often times out from Ollama queue contention
    # (extract()/duplicate-check sharing the same single-threaded queue),
    # not a dead ML service -- by the time our timeout fires, that queue has
    # usually drained, so one retry with a shorter timeout frequently
    # succeeds where giving up immediately would have silently landed every
    # real SOS on the confidence-0.0 fallback forever (no later retry existed
    # anywhere else in the pipeline).
    for timeout_s in (TRIAGE_TIMEOUT_S, TRIAGE_TIMEOUT_S / 2):
        try:
            result = await call_ml(
                "POST", "/ml/v1/triage", capability="triage", timeout_s=timeout_s,
                json=payload,
            )
            return _apply_keyword_escalation(result, text)
        except MLUnavailable:
            continue
    else:
        return {
            "acuity": "critical", "acuity_probs": {"critical": 1.0},
            "facility": "general", "facility_probs": {"general": 1.0},
            "confidence": 0.0, "needs_review": True,
            "fragility": bool(extracted.get("pregnant")) or (extracted.get("age") or 99) < 14,
            "mlc_flag": extracted.get("mechanism") in ("road_accident", "assault", "burn", "poisoning"),
            "model_version": "fallback:triage-unavailable",
        }


PHOTO_TRIAGE_TIMEOUT_S = 60.0  # moondream's cold load alone measured ~30s+; see photo_triage/model.py's own margin


async def photo_triage(image_b64: str) -> dict | None:
    """Photo attachment analysis (two independent reads: a vision LLM and a
    fine-tuned classifier, see services/ml photo_triage capability). On
    failure, the photo is still stored and viewable -- analysis is an
    enrichment, never a gate on anything the photo feature does."""
    try:
        return await call_ml("POST", "/ml/v1/photo-triage", capability="photo_triage",
                              timeout_s=PHOTO_TRIAGE_TIMEOUT_S, json={"image_b64": image_b64})
    except MLUnavailable:
        return None


async def prank_score(features: dict) -> dict | None:
    """technical.md §9.4: policy is 'never block' -- on failure, treat as
    not-suspicious and let dispatch proceed."""
    try:
        return await call_ml("POST", "/ml/v1/prank-score", capability="prank",
                              timeout_s=PRANK_TIMEOUT_S, json=features)
    except MLUnavailable:
        return None


async def duplicate_check(emergency: dict, candidates: list[dict]) -> dict | None:
    """On failure, skip duplicate handling for this call rather than block intake."""
    try:
        return await call_ml("POST", "/ml/v1/duplicate-check", capability="duplicate",
                              timeout_s=DUPLICATE_TIMEOUT_S,
                              json={"emergency": emergency, "candidates": candidates})
    except MLUnavailable:
        return None


async def resources(acuity: str, facility: str, extracted: dict,
                     profile_summary: str | None = None) -> dict | None:
    """On failure, prep checklist is simply empty -- not on the critical path."""
    try:
        return await call_ml(
            "POST", "/ml/v1/resources", capability="resources", timeout_s=RESOURCES_TIMEOUT_S,
            json={"acuity": acuity, "facility": facility, "extracted": extracted,
                  "profile_summary": profile_summary},
        )
    except MLUnavailable:
        return None


async def handover(transcript: str, extracted: dict, followup_answers: list[str],
                    profile: dict, triage_result: dict) -> dict | None:
    """On failure, hospital card falls back to raw extracted facts (handled by caller)."""
    try:
        return await call_ml(
            "POST", "/ml/v1/handover", capability="handover", timeout_s=HANDOVER_TIMEOUT_S,
            json={"transcript": transcript, "extracted": extracted,
                  "followup_answers": followup_answers, "profile": profile, "triage": triage_result},
        )
    except MLUnavailable:
        return None


async def followup_next(facility: str, acuity: str, extracted: dict,
                         answers: list[dict], language: str = "en") -> dict | None:
    """On failure, the patient's followup card simply stops advancing --
    caller treats None as done=True (no more questions) rather than blocking."""
    try:
        return await call_ml(
            "POST", "/ml/v1/followup/next", capability="followup", timeout_s=FOLLOWUP_TIMEOUT_S,
            json={"facility": facility, "acuity": acuity, "extracted": extracted,
                  "answers": answers, "language": language},
        )
    except MLUnavailable:
        return None


async def followup_parse(question_id: str, raw_answer: str, language: str = "en") -> dict | None:
    """On failure, store the raw text as-is (caller's fallback), parsed=None."""
    try:
        return await call_ml(
            "POST", "/ml/v1/followup/parse", capability="followup", timeout_s=FOLLOWUP_TIMEOUT_S,
            json={"question_id": question_id, "raw_answer": raw_answer, "language": language},
        )
    except MLUnavailable:
        return None


async def first_aid(facility: str, acuity: str, extracted: dict) -> dict | None:
    """Deterministic rule-table lookup on the ML side (first_aid:rule-table:v0),
    not a model -- still routed through call_ml for consistent timeout/base-URL
    handling. On failure, caller simply shows no first-aid card."""
    try:
        return await call_ml(
            "POST", "/ml/v1/first-aid", capability="first_aid", timeout_s=FIRST_AID_TIMEOUT_S,
            json={"facility": facility, "acuity": acuity, "extracted": extracted},
        )
    except MLUnavailable:
        return None
