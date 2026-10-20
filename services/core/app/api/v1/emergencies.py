"""A's file (work-distribution.md §2.2). POST /emergencies + GET /emergencies/{id}
(technical.md §7.3, §10.1). Runs process_emergency via FastAPI BackgroundTasks
as a stand-in for B's real arq job framework (app/jobs/worker.py, not built
yet) -- swap `background_tasks.add_task` for a real job enqueue once that
framework lands; the job body (domain/intake.process_emergency) doesn't change."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from pydantic import BaseModel
from sqlalchemy import text

from app.db.repos import emergencies as emergencies_repo
from app.db.repos import identity as identity_repo
from app.db.session import get_session
from app.domain import audit, followup, intake, tracking
from app.domain.privacy import project
from app.security.deps import CurrentUser, get_current_user
from app.security.tokens import hash_token, new_token


class FollowupAnswerRequest(BaseModel):
    question_id: str
    answer: str


class CancelRequest(BaseModel):
    reason: str | None = None

router = APIRouter()


def _authorize_emergency_access(user: CurrentUser, emergency: dict) -> None:
    """Who may read a given emergency, and under what role the response gets
    projected (domain/privacy.project). Ownership, not just role, decides
    this -- a paramedic may read THEIR OWN assigned case, not any case.

    user.id/hospital_id/ambulance_id are plain str (CurrentUser, security/deps.py);
    emergency[...] values come back from asyncpg as real uuid.UUID objects --
    `str == UUID` is always False regardless of value, so this rejected every
    single caller, including the patient who actually created the emergency.
    Same bug class already found and fixed elsewhere this session
    (domain/ops.py's claimer check, hospital.py's _check_scope)."""
    if user.role == "developer":  # the real "ops" role (db/migrations/0001_init.sql)
        return
    if user.role == "hospital_staff" and user.hospital_id and user.hospital_id == str(emergency.get("hospital_id")):
        return
    if user.role == "paramedic" and user.ambulance_id and user.ambulance_id == str(emergency.get("ambulance_id")):
        return
    if user.role == "patient" and emergency.get("caller_user_id") and user.id == str(emergency.get("caller_user_id")):
        return
    raise HTTPException(403, "not authorized to view this emergency")


@router.post("/emergencies", status_code=202)
async def create_emergency(
    background_tasks: BackgroundTasks,
    channel: str = Form(...),
    text: str | None = Form(None),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    accuracy_m: float | None = Form(None),
    caller_phone: str | None = Form(None),
    audio: UploadFile | None = File(None),
) -> dict:
    if channel not in ("app_button", "app_voice", "app_text", "sms"):
        raise HTTPException(400, "invalid channel")

    # The offer must never wait on ML. Audio is only read here; STT runs in the
    # background pipeline (intake.process_emergency) after dispatch has started.
    audio_bytes: bytes | None = None
    audio_name = "sos.webm"
    if channel == "app_voice" and audio is not None:
        audio_bytes = await audio.read()
        audio_name = audio.filename or audio_name
    transcript_text = text

    async with get_session() as session:
        caller_user_id = None
        if caller_phone:
            user = await identity_repo.get_or_create_patient_user(session, caller_phone)
            caller_user_id = user["id"]

        # "Call ambulance for them" (family space) sends no lat/lng at all --
        # the caller may not even be with the person they're calling for.
        # Fall back to that person's OWN last-known location (their phone,
        # their app, pinged periodically while open: POST /me/location),
        # not the caller's. Only when the request itself has no coordinates,
        # so a real app_button/app_voice SOS (which always has the actual
        # caller's live GPS) is never silently overridden.
        if lat is None and lng is None and caller_user_id:
            from sqlalchemy import text as sql_text  # `text` is shadowed here by this endpoint's own Form(text=...) SOS-message param
            loc_row = (await session.execute(
                sql_text("SELECT ST_Y(last_location::geometry) AS lat, ST_X(last_location::geometry) AS lng, "
                         "last_location_accuracy_m FROM users WHERE id = :uid AND last_location IS NOT NULL"),
                {"uid": caller_user_id},
            )).mappings().first()
            if loc_row:
                lat, lng, accuracy_m = loc_row["lat"], loc_row["lng"], loc_row["last_location_accuracy_m"]

        incident_id = await emergencies_repo.create_incident(session, lat=lat, lng=lng)

        raw_track_token, track_token_hash = new_token()
        emergency = await emergencies_repo.create_emergency(
            session, incident_id=incident_id, caller_user_id=caller_user_id, caller_phone=caller_phone,
            channel=channel, raw_text=text, lat=lat, lng=lng, accuracy_m=accuracy_m,
            family_track_token_hash=track_token_hash,
        )
        if transcript_text:
            await emergencies_repo.update_emergency(
                session, emergency["id"], expected_version=emergency["version"],
                transcript=transcript_text,
            )
        await emergencies_repo.create_patient_row(
            session, emergency_id=emergency["id"], user_id=caller_user_id, is_unknown=caller_user_id is None,
        )
        await audit.write(
            session, actor_type="user", actor_id=caller_phone or "anonymous",
            entity="emergencies", entity_id=emergency["id"], action="create",
            before=None, after={"channel": channel, "status": "received"},
        )
        await session.commit()

    # Starlette runs background tasks in order: dispatch first (~1s), then the slow ML pipeline.
    background_tasks.add_task(_run_dispatch, emergency["id"])
    background_tasks.add_task(_run_process_emergency, emergency["id"], audio_bytes, audio_name)

    return {
        "emergency_id": emergency["id"],
        "status": emergency["status"],
        "family_track_url": f"/track/{raw_track_token}",
        "call_108_fallback": False,
    }


async def _run_dispatch(emergency_id: str) -> None:
    async with get_session() as session:
        try:
            await intake.begin_dispatch(session, emergency_id)
            await session.commit()  # the outbox relay only sees offer.new after this commit
        except Exception:
            await session.rollback()
            # A bare `raise` here used to just vanish -- Starlette's
            # BackgroundTask runner has no visible failure path for the
            # caller (the 202 was already sent), and whatever happened
            # wasn't showing up in the Render log either. Log loudly so a
            # real exception is never silently indistinguishable from
            # "dispatch quietly found nothing."
            logging.getLogger("dispatch").exception("background dispatch failed for emergency %s", emergency_id)
            raise


async def _run_process_emergency(
    emergency_id: str, audio_bytes: bytes | None = None, audio_name: str = "sos.webm",
) -> None:
    async with get_session() as session:
        try:
            await intake.process_emergency(session, emergency_id, audio_bytes=audio_bytes, audio_name=audio_name)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


_ESCALATION_MESSAGES = {
    "no_ambulance": "No nearby ambulance has accepted yet. We're widening the search area -- this doesn't mean the system is down.",
    "no_hospital": "No hospital has confirmed a bed yet. We're widening the search and will stabilise at the nearest capable hospital if needed.",
    "mass_casualty": "Multiple people reported at this location. Coordinating resources across hospitals.",
    "system_anomaly": "A connected service is having trouble. Your request is still being handled.",
}


@router.get("/emergencies/{emergency_id}")
async def get_emergency(emergency_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    # Previously had no auth dependency at all -- anyone who guessed or saw
    # an emergency_id (e.g. from a URL shared for a different purpose) could
    # fetch the full clinical record, unfiltered, no role check whatsoever.
    async with get_session() as session:
        emergency = await emergencies_repo.get_emergency(session, emergency_id)
        if emergency is None:
            raise HTTPException(404, "emergency not found")
        # raise_escalation() never touches emergencies.status (it's a
        # separate ops/Telegram-facing table) -- a real "no ambulance
        # accepted yet" / "no hospital confirmed yet" case left the caller
        # staring at an unchanged "finding..." state forever, with nothing
        # to distinguish "still genuinely trying" from "something's broken",
        # which is exactly what spec's availability-status requirement
        # means. Surface the open escalation (if any) as an honest status
        # message, not a connection error.
        esc = (await session.execute(
            text("SELECT type FROM escalations WHERE emergency_id = :id AND status = 'open' "
                 "ORDER BY created_at DESC LIMIT 1"),
            {"id": emergency_id},
        )).mappings().first()
        # The frontend's EmergencyView.ambulance (api-types.ts) expects a
        # nested {registration_no, location, eta_sec, ...} object -- this
        # row only ever carried a flat ambulance_id, so that card was always
        # empty (not an error, just permanently undefined). See domain/tracking.py.
        ambulance_view = (
            await tracking.get_ambulance_view(session, str(emergency["ambulance_id"]), emergency)
            if emergency.get("ambulance_id") else None
        )
        # EmergencyView.route/leg (api-types.ts) -- the patient's own map
        # has never had a route line, regardless of GPS state, because
        # nothing ever computed one for this endpoint at all.
        route_view = (
            await tracking.get_patient_route_view(session, str(emergency["ambulance_id"]), emergency)
            if emergency.get("ambulance_id") else {"route": None, "leg": None}
        )
    _authorize_emergency_access(user, emergency)
    if esc:
        emergency = {**emergency, "escalation": {
            "type": esc["type"], "message": _ESCALATION_MESSAGES.get(esc["type"], "Still working on this -- taking longer than usual."),
        }}
    emergency = {**emergency, "ambulance": ambulance_view, **route_view}
    return project(user.role, emergency)


@router.get("/emergencies/{emergency_id}/followup")
async def get_followup(emergency_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    # lib/patient.ts's fetchFollowup() already tolerates a 404 gracefully
    # ("not implemented on this core yet: the card simply stays hidden") --
    # it existed as a documented gap, not a crash, but the real card never
    # showed because the route never existed at all.
    async with get_session() as session:
        emergency = await emergencies_repo.get_emergency(session, emergency_id)
        if emergency is None:
            raise HTTPException(404, "emergency not found")
        _authorize_emergency_access(user, emergency)
        state = await followup.get_followup_state(session, emergency_id)
    if state is None:
        raise HTTPException(404, "emergency not found")
    return state


@router.post("/emergencies/{emergency_id}/followup")
async def post_followup_answer(
    emergency_id: str, payload: FollowupAnswerRequest, user: CurrentUser = Depends(get_current_user),
) -> dict:
    async with get_session() as session:
        emergency = await emergencies_repo.get_emergency(session, emergency_id)
        if emergency is None:
            raise HTTPException(404, "emergency not found")
        _authorize_emergency_access(user, emergency)
        state = await followup.answer_followup_question(
            session, emergency_id, question_id=payload.question_id, raw_answer=payload.answer,
        )
        await session.commit()
    return state


@router.post("/emergencies/{emergency_id}/cancel")
async def cancel_emergency_endpoint(
    emergency_id: str, payload: CancelRequest, user: CurrentUser = Depends(get_current_user),
) -> dict:
    async with get_session() as session:
        try:
            await followup.cancel_emergency(
                session, emergency_id, caller_user_id=user.id, reason=payload.reason or "Cancelled by caller",
            )
            await session.commit()
            return {"status": "cancelled"}
        except PermissionError:
            raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "not your emergency"}})
        except ValueError as e:
            raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": str(e)}})
        except Exception as e:
            raise HTTPException(status_code=409, detail={"error": {"code": "CONFLICT", "message": str(e)}})


@router.get("/track/{raw_token}")
async def track_emergency(raw_token: str) -> dict:
    """Family tracking link (technical.md Section18/Section11): the raw
    token handed out at /emergencies creation time, verified by comparing
    its hash against family_track_token_hash -- the raw token itself is
    never stored. This endpoint did not exist at all before, despite
    create_emergency() already generating and returning family_track_url."""
    async with get_session() as session:
        emergency = await emergencies_repo.get_emergency_by_track_token_hash(session, hash_token(raw_token))
    if emergency is None:
        raise HTTPException(404, "invalid or expired tracking link")
    return project("family", emergency)
