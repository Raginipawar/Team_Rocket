"""Patient-facing followup Q&A (GET/POST /emergencies/{id}/followup) and SOS
cancellation (POST /emergencies/{id}/cancel). Neither endpoint existed on the
real backend at all -- the frontend's fetchFollowup() already silently
tolerated a 404 ("not implemented on this core yet: the card simply stays
hidden"), and the cancel button just threw an unhandled error."""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, update

from app.db.models import Ambulance, Emergency, Reservation
from app.db.repos import patient as patient_repo
from app.db.repos.reservations import release_reservation
from app.domain import audit
from app.domain.fsm.emergency_fsm import validate_transition
from app.integrations.ml import intake as ml_intake
from app.realtime import outbox


async def get_followup_state(db: AsyncSession, emergency_id: UUID) -> dict | None:
    em = await db.get(Emergency, emergency_id)
    if not em:
        return None

    answers = await patient_repo.list_followup_answers(db, str(emergency_id))
    answered_ids = {a["question_id"] for a in answers}
    answers_payload = [
        {"question_id": a["question_id"], "answer": str(a["answer_parsed"] if a["answer_parsed"] is not None else a["answer_raw"])}
        for a in answers
    ]

    result = await ml_intake.followup_next(
        facility=em.facility or "general", acuity=em.acuity or "urgent",
        extracted=em.extracted or {}, answers=answers_payload, language=em.language or "en",
    )
    if result is None:
        # ML unavailable -- same documented fallback pattern as everywhere
        # else in this pipeline: don't block the patient, just stop asking.
        return {"question": None, "done": True, "first_aid": None}

    question = result.get("question")
    done = result.get("done", True) or (question and question["id"] in answered_ids)
    first_aid = None
    if done:
        fa = await ml_intake.first_aid(facility=em.facility or "general", acuity=em.acuity or "urgent",
                                        extracted=em.extracted or {})
        if fa:
            first_aid = {"protocol_id": fa["protocol_id"], "title": fa["title"],
                         "steps": fa["steps"], "donts": fa["donts"]}

    return {"question": None if done else question, "done": bool(done), "first_aid": first_aid}


async def answer_followup_question(
    db: AsyncSession, emergency_id: UUID, *, question_id: str, raw_answer: str,
) -> dict:
    em = await db.get(Emergency, emergency_id)
    if not em:
        raise ValueError("Emergency not found")

    parsed_result = await ml_intake.followup_parse(question_id=question_id, raw_answer=raw_answer,
                                                     language=em.language or "en")
    parsed = parsed_result.get("parsed") if parsed_result else None

    await patient_repo.record_followup_answer(
        db, str(emergency_id), question_id=question_id, answer_raw=raw_answer,
        answer_parsed=parsed, language=em.language or "en",
    )
    return await get_followup_state(db, emergency_id)


async def cancel_emergency(db: AsyncSession, emergency_id: UUID, *, caller_user_id: str, reason: str) -> None:
    em = await db.get(Emergency, emergency_id)
    if not em:
        raise ValueError("Emergency not found")
    if not em.caller_user_id or str(em.caller_user_id) != str(caller_user_id):
        raise PermissionError("not your emergency")

    validate_transition(em.status, "cancelled")
    before_status = em.status
    em.status = "cancelled"
    em.version += 1

    # Mirrors handle_refused_transport's own ambulance-freeing logic -- a
    # cancelled case shouldn't leave its responding ambulance stuck
    # "available"-blocked forever, same real status value confirmed earlier
    # this session ('idle' is not a real AmbulanceStatus value).
    if em.ambulance_id:
        await db.execute(update(Ambulance).where(Ambulance.id == em.ambulance_id).values(status='available'))

    res = (await db.execute(
        select(Reservation).where(Reservation.emergency_id == emergency_id, Reservation.status.in_(['held', 'confirmed']))
    )).scalar_one_or_none()
    if res:
        await release_reservation(db, res.id, "released")

    await audit.write(
        db, actor_type="user", actor_id=str(caller_user_id), entity="emergencies",
        entity_id=emergency_id, action="cancel", before={"status": before_status},
        after={"status": "cancelled", "reason": reason},
    )
    await outbox.emit(db, channel=f"emergency:{emergency_id}", event="emergency.status",
                       data={"status": "cancelled", "reason": reason})
