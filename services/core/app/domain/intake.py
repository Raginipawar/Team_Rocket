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


async def _update_retry(session: AsyncSession, emergency_id: str, **fields) -> dict | None:
    """update_emergency with optimistic locking, re-reading the version on conflict.
    Dispatch and the paramedic's app bump the row version while this slow pipeline runs."""
    for _ in range(5):
        fresh = await emergencies_repo.get_emergency(session, emergency_id)
        if fresh is None:
            return None
        try:
            await emergencies_repo.update_emergency(
                session, emergency_id, expected_version=fresh["version"], **fields)
            return fresh
        except emergencies_repo.VersionConflict:
            continue
    raise RuntimeError(f"could not update emergency {emergency_id}: repeated version conflicts")


async def begin_dispatch(session: AsyncSession, emergency_id: str) -> None:
    """Fast path, runs the moment an SOS is saved. No ML in front of it."""
    em = await emergencies_repo.get_emergency(session, emergency_id)
    if em is None or em["status"] != "received":
        return
    await _update_retry(session, emergency_id, status="dispatching")
    await outbox.emit(session, channel=f"emergency:{emergency_id}", event="emergency.status",
                      data={"status": "dispatching", "version": em["version"] + 1})
    await dispatch.start_dispatch(session, emergency_id=emergency_id, priority=True, reason="sos_received")


async def process_emergency(
    session: AsyncSession, emergency_id: str, *, audio_bytes: bytes | None = None, audio_name: str = "sos.webm",
) -> None:
    emergency = await emergencies_repo.get_emergency(session, emergency_id)
    if emergency is None:
        logger.error("process_emergency: emergency %s not found", emergency_id)
        return

    # Step 4.0: speech-to-text, now in the background (dispatch no longer waits for it).
    if audio_bytes:
        # Whisper's own language auto-detection is unreliable for romanized/
        # code-switched Hindi/Marathi speech (a well-known real failure mode
        # -- it can misdetect the script entirely, producing garbage in the
        # wrong language's vocabulary). The app already knows which language
        # the caller selected in the UI (sent as `language` on emergency
        # creation) but this call never passed it through -- found by a real
        # Marathi test producing an empty transcript, not by reading the code.
        stt_result = await ml.stt(audio_bytes, audio_name, lang_hint=emergency.get("language"))
        if stt_result:
            await _update_retry(
                session, emergency_id,
                transcript=stt_result.get("transcript") or emergency.get("transcript"),
                language=stt_result.get("language"), stt_confidence=stt_result.get("confidence"),
            )
            await session.commit()
            emergency = await emergencies_repo.get_emergency(session, emergency_id)
            await outbox.emit(session, channel=f"emergency:{emergency_id}", event="emergency.transcript",
                              data={"transcript": emergency.get("transcript")})
            if emergency.get("ambulance_id"):
                await outbox.emit(session, channel=f"ambulance:{emergency['ambulance_id']}",
                                  event="emergency.transcript",
                                  data={"emergency_id": emergency_id, "transcript": emergency.get("transcript")})
            await session.commit()

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
        gazetteer=location.PgTrgmGazetteerLookup(session),
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

    # Never touches `status`: dispatch/paramedic flow owns it, and this must not overwrite at_scene etc.
    fresh = await _update_retry(
        session, emergency_id,
        extracted=_json(extracted),
        location_source=location_source,
        ai_acuity=triage_result["acuity"], ai_facility=triage_result["facility"],
        ai_confidence=triage_result["confidence"], needs_review=triage_result["needs_review"],
        fragility=triage_result["fragility"], mlc_flag=triage_result["mlc_flag"],
        required_ambulance_type=required_ambulance_type,
        prank_score=(prank_result or {}).get("score"),
        duplicate_of=(duplicate_result or {}).get("duplicate_of"),
        predicted_resources=_json(resources_result or {}),
    )
    if fresh is None:
        return
    fresh = await emergencies_repo.get_emergency(session, emergency_id)

    await audit.write(
        session, actor_type="ai", actor_id="triage", entity="emergencies", entity_id=emergency_id,
        action="triage_complete", before=None, after=triage_result,
        model_version=triage_result.get("model_version"),
    )
    payload = {
        "acuity": triage_result["acuity"], "facility": triage_result["facility"],
        "confidence": triage_result["confidence"], "needs_review": triage_result["needs_review"],
        "confirmed": False,
    }
    await outbox.emit(session, channel=f"emergency:{emergency_id}", event="emergency.triage", data=payload)
    if fresh.get("ambulance_id"):
        await outbox.emit(session, channel=f"ambulance:{fresh['ambulance_id']}",
                          event="emergency.triage", data={"emergency_id": emergency_id, **payload})

    # Prank / duplicate results flag the case for human review; they never cancel a real emergency.
    if (prank_result or {}).get("score", 0) >= 0.8 or (duplicate_result or {}).get("same_incident"):
        await audit.write(
            session, actor_type="ai", actor_id="intake", entity="emergencies", entity_id=emergency_id,
            action="flagged_for_review", before=None,
            after={"prank": prank_result, "duplicate": duplicate_result},
        )

    patient_count = extracted.get("patient_count", 1)
    if patient_count >= MCI_PATIENT_THRESHOLD:
        await escalation.raise_escalation(
            session, type="mass_casualty", emergency_id=emergency_id,
            context={"summary": f"{patient_count} patients reported at one location"},
        )


# What a confident photo read actually DOES, not just what it says --
# labeling a visibly bleeding photo "bleeding" next to the photo itself is
# redundant (anyone looking at it can already see that); feeding it into
# the same resource-prediction/first-aid machinery the rest of intake.py
# already has is not. Deliberately NOT touching ai_acuity/ai_facility here
# -- those drive dispatch/hospital matching, which may already be acting on
# the pre-photo values by the time this background analysis completes;
# silently rewriting them after the fact would desync what's stored from
# what dispatch actually did. Resources (advisory, additive, never gates
# anything) and a direct first-aid tip (shown immediately, not routed
# through the acuity-driven lookup) are safe regardless of what phase the
# emergency is already in.
PHOTO_RESOURCE_HINTS: dict[str, list[dict]] = {
    "bleeding": [{"item": "pressure_bandage", "prob": 0.8}, {"item": "gauze", "prob": 0.8}],
    "burn": [{"item": "burn_dressing", "prob": 0.8}, {"item": "saline", "prob": 0.7}],
    "bruise_fracture": [{"item": "splint", "prob": 0.6}],
}
PHOTO_FIRST_AID: dict[str, str] = {
    "bleeding": "Photo shows visible bleeding -- apply firm, direct pressure to the wound with a clean cloth and keep it elevated if possible until the ambulance arrives.",
    "burn": "Photo shows a visible burn -- cool the area with clean running water for several minutes. Do not apply ice, butter, or ointments.",
    "bruise_fracture": "Photo shows possible bruising or a suspected fracture -- keep the area still and supported. Do not try to straighten or move an injured limb.",
}


async def process_photo(session: AsyncSession, emergency_id: str, image_b64: str) -> None:
    """Photo attachment, same 'the real pipeline is never blocked by ML'
    principle as process_emergency's own STT/triage calls -- the photo is
    already saved (api/v1/emergencies.py's upload endpoint does that
    synchronously, before this background task even starts) by the time
    this runs, so a slow/unavailable ML service only delays the analysis
    enrichment, never the upload itself."""
    analysis = await ml.photo_triage(image_b64)
    if analysis is None:
        # ml.photo_triage() already retries once -- if it's still None here,
        # don't leave the photo stuck on "Analyzing..." forever with no way
        # for the client to ever resolve it (there is no later retry
        # anywhere else in this pipeline, same bug class as the earlier
        # triage confidence-stuck-at-0 issue). An honest "couldn't analyze"
        # result the UI can render is better than a permanently pending one.
        analysis = {
            "vision_llm": {"label": "unclear", "severity": "unknown", "description": "AI photo analysis unavailable", "confidence": 0.0},
            "finetuned_classifier": {"label": "unclear", "confidence": 0.0},
            "agreement": False, "needs_review": True,
            "model_version": "fallback:photo-triage-unavailable",
        }

    label = (analysis.get("finetuned_classifier") or {}).get("label", "unclear")
    # Only act on a read that's actually trustworthy -- needs_review already
    # encodes "the two models disagreed, or either was low-confidence,"
    # exactly the case where auto-adding resources or pushing a first-aid
    # tip could be acting on a wrong read.
    confident = not analysis.get("needs_review") and label in PHOTO_RESOURCE_HINTS

    update_fields: dict[str, str] = {"photo_analysis": _json(analysis)}
    if confident:
        current = await emergencies_repo.get_emergency(session, emergency_id)
        existing = (current or {}).get("predicted_resources")
        existing = existing if isinstance(existing, dict) else {}
        existing_items = existing.get("resources", []) if isinstance(existing.get("resources"), list) else []
        existing_names = {i.get("item") for i in existing_items if isinstance(i, dict)}
        new_items = [h for h in PHOTO_RESOURCE_HINTS[label] if h["item"] not in existing_names]
        if new_items:
            update_fields["predicted_resources"] = _json({**existing, "resources": existing_items + new_items})

    fresh = await _update_retry(session, emergency_id, **update_fields)
    if fresh is None:
        return
    await audit.write(
        session, actor_type="ai", actor_id="photo_triage", entity="emergencies", entity_id=emergency_id,
        action="photo_analysis_complete", before=None, after=analysis,
    )
    payload = {"photo_analysis": analysis}
    await outbox.emit(session, channel=f"emergency:{emergency_id}", event="emergency.photo_analysis", data=payload)
    if fresh.get("ambulance_id"):
        await outbox.emit(session, channel=f"ambulance:{fresh['ambulance_id']}",
                          event="emergency.photo_analysis", data={"emergency_id": emergency_id, **payload})

    if confident and label in PHOTO_FIRST_AID:
        await outbox.emit(session, channel=f"emergency:{emergency_id}", event="alert",
                          data={"message": PHOTO_FIRST_AID[label]})


def _json(obj: dict) -> str:
    import json
    return json.dumps(obj)
