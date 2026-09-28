"""A's file (work-distribution.md §2.2). technical.md §12.1: webhook returns
200 in <100ms and processes in the background; dedupe by gateway message_id.
Auth by shared secret (SMS_WEBHOOK_SECRET)."""

import os

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from sqlalchemy import text

from app.db.repos import emergencies as emergencies_repo
from app.db.repos import identity as identity_repo
from app.db.session import get_session
from app.domain import audit, intake
from app.integrations.sms.parser import FollowupAnswer, NewEmergency, ParamedicCommand, PrankVerification, parse_inbound
from app.security.tokens import new_token

router = APIRouter()

SMS_WEBHOOK_SECRET = os.getenv("SMS_WEBHOOK_SECRET", "dev-insecure-sms-secret")


@router.post("/webhooks/sms", status_code=200)
async def sms_webhook(
    body: dict, background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None),
) -> dict:
    if x_webhook_secret != SMS_WEBHOOK_SECRET:
        raise HTTPException(401, "invalid webhook secret")

    from_phone = body["from"]
    message_body = body["body"]
    gateway_message_id = body["message_id"]

    async with get_session() as session:
        already_seen = (await session.execute(
            text("SELECT 1 FROM sms_messages WHERE gateway_message_id = :mid"),
            {"mid": gateway_message_id},
        )).scalar_one_or_none()
        if already_seen:
            return {"status": "duplicate_ignored"}

        await session.execute(
            text(
                "INSERT INTO sms_messages (direction, phone, body, gateway_message_id, status) "
                "VALUES ('in', :phone, :body, :mid, 'received')"
            ),
            {"phone": from_phone, "body": message_body, "mid": gateway_message_id},
        )
        await session.commit()

    background_tasks.add_task(_process_inbound_sms, from_phone, message_body)
    return {"status": "accepted"}


async def _find_open_followup(session, phone: str) -> dict | None:
    row = (await session.execute(
        text(
            "SELECT id AS emergency_id FROM emergencies "
            "WHERE caller_phone = :phone AND status NOT IN ('closed','cancelled','handed_off','merged_duplicate') "
            "AND received_at > now() - interval '60 minutes' "
            "ORDER BY received_at DESC LIMIT 1"
        ),
        {"phone": phone},
    )).mappings().first()
    if row is None:
        return None
    return {"emergency_id": str(row["emergency_id"]), "question_id": None}


async def _process_inbound_sms(from_phone: str, message_body: str) -> None:
    async with get_session() as session:
        open_followup = await _find_open_followup(session, from_phone)
        parsed = parse_inbound(message_body, open_followup)

        if isinstance(parsed, ParamedicCommand):
            await _handle_paramedic_command(session, from_phone, parsed)
        elif isinstance(parsed, PrankVerification):
            await _handle_prank_verification(session, from_phone)
        elif isinstance(parsed, FollowupAnswer):
            await _handle_followup_answer(session, parsed, message_body)
        elif isinstance(parsed, NewEmergency):
            await _handle_new_emergency(session, from_phone, message_body)

        await session.commit()


async def _handle_paramedic_command(session, phone: str, cmd: ParamedicCommand) -> None:
    row = (await session.execute(
        text("SELECT id, status, version FROM emergencies WHERE id::text LIKE :short_id || '%' ORDER BY received_at DESC LIMIT 1"),
        {"short_id": cmd.emergency_short_id},
    )).mappings().first()
    if row is None:
        return

    status_map = {"ARRIVED": "at_scene", "ONBOARD": "patient_on_board"}
    if cmd.command in status_map:
        await session.execute(
            text("UPDATE emergencies SET status = :status, version = version + 1 WHERE id = :id AND version = :v"),
            {"status": status_map[cmd.command], "id": row["id"], "v": row["version"]},
        )
    await audit.write(session, actor_type="user", actor_id=phone, entity="emergencies", entity_id=row["id"],
                       action="sms_paramedic_command", before=None, after={"command": cmd.command})


async def _handle_prank_verification(session, phone: str) -> None:
    await session.execute(
        text(
            "UPDATE emergencies SET prank_verified = true WHERE id = ("
            "  SELECT id FROM emergencies WHERE caller_phone = :phone "
            "  AND status NOT IN ('closed','cancelled') ORDER BY received_at DESC LIMIT 1"
            ")"
        ),
        {"phone": phone},
    )


async def _handle_followup_answer(session, answer: FollowupAnswer, raw_text: str) -> None:
    await session.execute(
        text("INSERT INTO followup_answers (emergency_id, question_id, answer_raw) VALUES (:eid, :qid, :raw)"),
        {"eid": answer.emergency_id, "qid": answer.question_id or "unknown", "raw": raw_text},
    )


async def _handle_new_emergency(session, phone: str, text_body: str) -> None:
    user = await identity_repo.get_or_create_patient_user(session, phone)
    incident_id = await emergencies_repo.create_incident(session, lat=None, lng=None)
    raw_track_token, track_token_hash = new_token()
    emergency = await emergencies_repo.create_emergency(
        session, incident_id=incident_id, caller_user_id=user["id"], caller_phone=phone,
        channel="sms", raw_text=text_body, lat=None, lng=None, accuracy_m=None,
        family_track_token_hash=track_token_hash,
    )
    await emergencies_repo.create_patient_row(session, emergency_id=emergency["id"], user_id=user["id"], is_unknown=False)
    await audit.write(session, actor_type="user", actor_id=phone, entity="emergencies", entity_id=emergency["id"],
                       action="create", before=None, after={"channel": "sms"})
    await session.flush()  # emergency row must be visible to process_emergency's own queries, without ending the transaction
    await intake.process_emergency(session, emergency["id"])
