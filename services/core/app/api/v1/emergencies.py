"""A's file (work-distribution.md §2.2). POST /emergencies + GET /emergencies/{id}
(technical.md §7.3, §10.1). Runs process_emergency via FastAPI BackgroundTasks
as a stand-in for B's real arq job framework (app/jobs/worker.py, not built
yet) -- swap `background_tasks.add_task` for a real job enqueue once that
framework lands; the job body (domain/intake.process_emergency) doesn't change."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from app.db.repos import emergencies as emergencies_repo
from app.db.repos import identity as identity_repo
from app.db.session import get_session
from app.domain import audit, intake
from app.domain.privacy import project
from app.integrations.ml import intake as ml_intake
from app.security.deps import CurrentUser, get_current_user
from app.security.tokens import hash_token, new_token

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

    # app_voice sent an audio file, but nothing anywhere ever read it -- no
    # UploadFile param existed here, so FastAPI silently dropped the
    # multipart field, and domain/intake.process_emergency's own comment
    # ("STT already ran, if voice, before this job") describes a step that
    # never actually ran. ml_intake.stt() was already fully wired against
    # the real /ml/v1/stt capability, just never called. Transcribe here,
    # synchronously, before the row exists committed -- process_emergency
    # reads transcript fresh from the DB when its background task fires, so
    # it only needs to be written before that, not before the HTTP response.
    transcript_text = text
    stt_language = None
    stt_confidence = None
    if channel == "app_voice" and audio is not None:
        audio_bytes = await audio.read()
        stt_result = await ml_intake.stt(audio_bytes, audio.filename or "sos.webm")
        if stt_result:
            transcript_text = stt_result.get("transcript") or text
            stt_language = stt_result.get("language")
            stt_confidence = stt_result.get("confidence")
        # stt_result is None on ML-unavailable/timeout -- per technical.md §9.1
        # the emergency still gets created on whatever text/button data it has;
        # transcript just stays whatever the client sent (usually empty).

    async with get_session() as session:
        caller_user_id = None
        if caller_phone:
            user = await identity_repo.get_or_create_patient_user(session, caller_phone)
            caller_user_id = user["id"]

        incident_id = await emergencies_repo.create_incident(session, lat=lat, lng=lng)

        raw_track_token, track_token_hash = new_token()
        emergency = await emergencies_repo.create_emergency(
            session, incident_id=incident_id, caller_user_id=caller_user_id, caller_phone=caller_phone,
            channel=channel, raw_text=text, lat=lat, lng=lng, accuracy_m=accuracy_m,
            family_track_token_hash=track_token_hash,
        )
        if transcript_text or stt_language:
            await emergencies_repo.update_emergency(
                session, emergency["id"], expected_version=emergency["version"],
                transcript=transcript_text, language=stt_language, stt_confidence=stt_confidence,
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

    background_tasks.add_task(_run_process_emergency, emergency["id"])

    return {
        "emergency_id": emergency["id"],
        "status": emergency["status"],
        "family_track_url": f"/track/{raw_track_token}",
        "call_108_fallback": False,
    }


async def _run_process_emergency(emergency_id: str) -> None:
    async with get_session() as session:
        try:
            await intake.process_emergency(session, emergency_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@router.get("/emergencies/{emergency_id}")
async def get_emergency(emergency_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    # Previously had no auth dependency at all -- anyone who guessed or saw
    # an emergency_id (e.g. from a URL shared for a different purpose) could
    # fetch the full clinical record, unfiltered, no role check whatsoever.
    async with get_session() as session:
        emergency = await emergencies_repo.get_emergency(session, emergency_id)
    if emergency is None:
        raise HTTPException(404, "emergency not found")
    _authorize_emergency_access(user, emergency)
    return project(user.role, emergency)


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
