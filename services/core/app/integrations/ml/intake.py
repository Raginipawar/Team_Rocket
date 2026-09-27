"""Typed wrappers for the ML capabilities the intake pipeline calls (A's
domain: technical.md §9.1-9.6, §9.9-9.10). Timeouts and fallback behaviour are
copied verbatim from the spec -- the caller (domain/intake.py) decides what to
do with a fallback result, this module only knows how to reach ML and what
"unavailable" means per capability."""

from .base import MLUnavailable, call_ml

STT_TIMEOUT_S = 8.0
EXTRACT_TIMEOUT_S = 6.0
TRIAGE_TIMEOUT_S = 3.0
PRANK_TIMEOUT_S = 5.0
DUPLICATE_TIMEOUT_S = 5.0
RESOURCES_TIMEOUT_S = 5.0
HANDOVER_TIMEOUT_S = 6.0


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


async def triage(text: str, extracted: dict, profile_summary: str | None = None,
                  followup_answers: list[str] | None = None) -> dict:
    """technical.md §9.3: on failure, safe-side default -- acuity critical,
    facility general, needs_review=true (forces ALS dispatch). Never returns
    None: callers rely on this dict always having acuity/facility/needs_review."""
    try:
        return await call_ml(
            "POST", "/ml/v1/triage", capability="triage", timeout_s=TRIAGE_TIMEOUT_S,
            json={
                "text": text, "extracted": extracted,
                "profile_summary": profile_summary,
                "followup_answers": followup_answers or [],
            },
        )
    except MLUnavailable:
        return {
            "acuity": "critical", "acuity_probs": {"critical": 1.0},
            "facility": "general", "facility_probs": {"general": 1.0},
            "confidence": 0.0, "needs_review": True,
            "fragility": bool(extracted.get("pregnant")) or (extracted.get("age") or 99) < 14,
            "mlc_flag": extracted.get("mechanism") in ("road_accident", "assault", "burn", "poisoning"),
            "model_version": "fallback:triage-unavailable",
        }


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
