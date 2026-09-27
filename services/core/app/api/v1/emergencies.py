"""A's file (work-distribution.md §2.2). POST /emergencies + GET /emergencies/{id}
(technical.md §7.3, §10.1). Runs process_emergency via FastAPI BackgroundTasks
as a stand-in for B's real arq job framework (app/jobs/worker.py, not built
yet) -- swap `background_tasks.add_task` for a real job enqueue once that
framework lands; the job body (domain/intake.process_emergency) doesn't change."""

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException

from app.db.repos import emergencies as emergencies_repo
from app.db.repos import identity as identity_repo
from app.db.session import get_session
from app.domain import audit, intake
from app.security.tokens import new_token

router = APIRouter()


@router.post("/emergencies", status_code=202)
async def create_emergency(
    background_tasks: BackgroundTasks,
    channel: str = Form(...),
    text: str | None = Form(None),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    accuracy_m: float | None = Form(None),
    caller_phone: str | None = Form(None),
) -> dict:
    if channel not in ("app_button", "app_voice", "app_text", "sms"):
        raise HTTPException(400, "invalid channel")

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
async def get_emergency(emergency_id: str) -> dict:
    async with get_session() as session:
        emergency = await emergencies_repo.get_emergency(session, emergency_id)
    if emergency is None:
        raise HTTPException(404, "emergency not found")
    return emergency
