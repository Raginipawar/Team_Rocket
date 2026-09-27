"""A's file (work-distribution.md §2.2). The `process_emergency` async job
(technical.md §10.1). Orchestrates STT -> extraction -> location resolution ->
[triage, prank, duplicate, resources in parallel] -> MCI check -> triaged ->
dispatching, writing every step to the real tables and auditing every
decision (technical.md §23 Definition of Done).

Calls into B's not-yet-built pieces (audit.write, raise_escalation,
start_dispatch, outbox.emit) go through the DRAFT stubs in domain/audit.py,
domain/escalation.py, domain/dispatch.py, realtime/outbox.py -- swap nothing
here when B's real versions land, since the call signatures are frozen
per work-distribution.md §4."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repos import emergencies as emergencies_repo
from app.db.repos import identity as identity_repo
from app.domain import audit, dispatch, escalation, location
from app.integrations.ml import intake as ml
from app.realtime import outbox

logger = logging.getLogger("intake")

MCI_PATIENT_THRESHOLD = 5


class NullGazetteer:
    """Stand-in until B seeds the `landmarks` table from the OSM gazetteer
    (technical.md §22). Always misses, so the chain falls through to
    profile_home / ask-for-landmark -- never silently invents a location."""

    async def match(self, landmark_text: str, *, near=None):
        return None


async def process_emergency(session: AsyncSession, emergency_id: str) -> None:
    emergency = await emergencies_repo.get_emergency(session, emergency_id)
    if emergency is None:
        logger.error("process_emergency: emergency %s not found", emergency_id)
        return

    text_for_extraction = emergency.get("transcript") or ""
    language = emergency.get("language") or "en"
    extracted: dict = {}

    # Step 4.1: extraction (STT already ran, if voice, before this job -- the
    # transcript is already on the row by the time this job picks it up).
    if text_for_extraction:
        extracted = await ml.extract(text_for_extraction, language) or {}

    # Step 3: location resolution.
    resolved = await location.resolve_location(
        gps=(emergency["lat"], emergency["lng"]) if emergency.get("lat") is not None else None,
        accuracy_m=emergency.get("location_accuracy_m"),
        landmark_text=extracted.get("landmark"),
        profile_home=None,  # wired once db/repos/identity.get_health_profile has a real caller_user_id
        gazetteer=NullGazetteer(),
    )
    location_source = resolved.source if resolved else "unresolved"

    # Step 4: triage, prank-score, duplicate-check, resources -- in parallel.
    triage_task = ml.triage(text_for_extraction, extracted)
    prank_task = ml.prank_score({
        "phone": "", "channel": "app_text", "hour": 0, "calls_24h": 0, "calls_7d": 0,
        "prior_prank_flags": 0, "transcript_len": len(text_for_extraction),
        "coherence": extracted.get("coherence", 0.5), "location_jump_km": 0.0, "text_repeat_ratio": 0.0,
    })
    duplicate_task = ml.duplicate_check(
        {"text": text_for_extraction, "location": {}, "time": "", "extracted": extracted}, [],
    )
    resources_task = ml.resources("critical", "general", extracted)  # placeholder acuity/facility until triage returns

    triage_result, prank_result, duplicate_result, _resources_placeholder = await asyncio.gather(
        triage_task, prank_task, duplicate_task, resources_task,
    )

    resources_result = await ml.resources(triage_result["acuity"], triage_result["facility"], extracted)

    required_ambulance_type = "ALS" if (
        triage_result["acuity"] == "critical" or triage_result["needs_review"]
    ) else "BLS"

    await emergencies_repo.update_emergency(
        session, emergency_id, expected_version=emergency["version"],
        extracted=_json(extracted),
        location_source=location_source,
        ai_acuity=triage_result["acuity"], ai_facility=triage_result["facility"],
        ai_confidence=triage_result["confidence"], needs_review=triage_result["needs_review"],
        fragility=triage_result["fragility"], mlc_flag=triage_result["mlc_flag"],
        required_ambulance_type=required_ambulance_type,
        prank_score=(prank_result or {}).get("score"),
        duplicate_of=(duplicate_result or {}).get("duplicate_of"),
        predicted_resources=_json(resources_result or {}),
        status="triaged",
    )

    await audit.write(
        session, actor_type="ai", actor_id="triage", entity="emergencies", entity_id=emergency_id,
        action="triage_complete", before={"status": "received"}, after=triage_result,
        model_version=triage_result.get("model_version"),
    )
    await outbox.emit(session, channel=f"emergency:{emergency_id}", event="emergency.triage", data={
        "acuity": triage_result["acuity"], "facility": triage_result["facility"],
        "confidence": triage_result["confidence"], "needs_review": triage_result["needs_review"],
        "confirmed": False,
    })

    if duplicate_result and duplicate_result.get("same_incident") and not duplicate_result.get("additional_patients"):
        await emergencies_repo.update_emergency(
            session, emergency_id, expected_version=emergency["version"] + 1, status="merged_duplicate",
        )
        await outbox.emit(session, channel=f"emergency:{emergency_id}", event="emergency.status",
                           data={"status": "merged_duplicate", "version": emergency["version"] + 2})
        return

    patient_count = extracted.get("patient_count", 1)
    if patient_count >= MCI_PATIENT_THRESHOLD:
        await escalation.raise_escalation(
            session, type="mass_casualty", emergency_id=emergency_id,
            context={"summary": f"{patient_count} patients reported at one location"},
        )

    await emergencies_repo.update_emergency(
        session, emergency_id, expected_version=emergency["version"] + 1, status="dispatching",
    )
    await outbox.emit(session, channel=f"emergency:{emergency_id}", event="emergency.status",
                       data={"status": "dispatching", "version": emergency["version"] + 2})

    await dispatch.start_dispatch(session, emergency_id=emergency_id, priority=triage_result["acuity"] == "critical",
                                   reason="triage_confirmed")


def _json(obj: dict) -> str:
    import json
    return json.dumps(obj)
