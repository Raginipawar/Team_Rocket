from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repos.rooms import lock_free_room_skip_locked
from app.db.repos.resources import decrement_resource
from app.db.repos.reservations import create_reservation, release_reservation
from app.domain.fsm.transition import apply_transition
from app.domain.fsm.emergency_fsm import validate_transition as validate_emergency_transition
from app.db.models import Emergency, HospitalRequest, Reservation, Room # type: ignore
from sqlalchemy import update
import json

# technical.md §11.5 — acceptable_room_types by facility. The previous
# version of this function passed the raw `facility` string (e.g. "cardiac")
# directly as if it were a room `type` value, but room types are
# er_bed/resus_bay/trauma_bay/etc -- that string never matched any real row,
# so lock_free_room_skip_locked silently always returned None and no room
# was ever actually held. Found by running this against a real seeded room.
ACCEPTABLE_ROOM_TYPES = {
    "cardiac": ["resus_bay", "er_bed"], "trauma": ["trauma_bay", "resus_bay"],
    "obstetric": ["labour_room"], "pediatric": ["pediatric_er", "er_bed"],
    "burns": ["burns_unit"], "stroke": ["resus_bay", "er_bed"],
    "respiratory": ["resus_bay", "er_bed"], "poisoning": ["resus_bay", "er_bed"],
    "general": ["er_bed"],
}


async def create_hospital_request_with_hold(
    db: AsyncSession,
    emergency_id: UUID,
    hospital_id: UUID,
    rank: int,
    features: dict,
    explanation: list,
    acuity: str,
    facility: str,
    is_family_choice: bool = False,
    score: float | None = None,
    required_resources: list[str] | None = None,
) -> HospitalRequest:
    acceptable_types = ACCEPTABLE_ROOM_TYPES.get(facility, ["er_bed"])
    room = await lock_free_room_skip_locked(db, hospital_id, acceptable_types)
    # Books whatever the real predicted-resources list says is actually
    # needed (selection.py's start_selection now calls ml.resources() for
    # this) instead of always decrementing a hardcoded "ventilator" --
    # falls back to ["ventilator"] for any caller that doesn't pass one
    # (e.g. ops.py's manual_override) so this stays backward compatible.
    resources_to_book = required_resources or ["ventilator"]
    booked_resources = []
    for resource_type in resources_to_book:
        if await decrement_resource(db, hospital_id, resource_type, 1):
            booked_resources.append(resource_type)

    expires = datetime.utcnow() + timedelta(minutes=5)
    res = await create_reservation(
        db,
        hospital_id=hospital_id,
        emergency_id=emergency_id,
        status="held",
        room_id=room.id if room else None,
        hold_expires_at=expires
    )

    # Without a reservation_items row, release_reservation has nothing to
    # find on reject/timeout/refused-transport -- the decremented resource
    # would leak permanently (available/reserved never credited back).
    if booked_resources:
        from app.db.models import ReservationItem
        for resource_type in booked_resources:
            db.add(ReservationItem(reservation_id=res.id, kind="resource", resource_type=resource_type, quantity=1))

    if room:
        # technical.md §11.3 step 1's second half -- the actual double-booking
        # guard. SKIP LOCKED only holds the row lock for the duration of this
        # transaction; without this UPDATE the room's status column never
        # actually changes, so a second concurrent request could select the
        # same "free" room again once this transaction's lock releases. This
        # was missing entirely -- the function locked the room but never
        # marked it reserved.
        room_update = await db.execute(
            update(Room).where(Room.id == room.id, Room.status == "free")
            .values(status="reserved", reservation_id=res.id, version=Room.version + 1)
        )
        if room_update.rowcount == 0:
            # Someone else grabbed it between the SELECT FOR UPDATE and here
            # (shouldn't happen under SKIP LOCKED, but don't silently proceed
            # as if we hold a room we don't).
            room = None

    req = HospitalRequest(
        emergency_id=emergency_id,
        hospital_id=hospital_id,
        reservation_id=res.id,
        status="pending",
        rank=rank,
        score=score,
        explanation=explanation,
        features=features,
        is_family_choice=is_family_choice
    )
    db.add(req)

    em = await db.get(Emergency, emergency_id)
    if em and em.status != "hospital_selecting":
        # Real FSM graph (fsm/emergency_fsm.py) has no direct at_scene ->
        # hospital_selecting edge -- it must pass through patient_on_board
        # first. The real UI has no separate "patient on board" action
        # (TriageConfirmSheet goes straight to "Choosing the best
        # hospital"), so that intermediate hop happens here, implicitly,
        # as part of the same call. Validating straight to hospital_selecting
        # without this raised on the very first live test, and because the
        # candidate loop above swallows it in a broad except, the failure
        # was silent: a hospital_request got created and committed anyway
        # while the emergency's status never actually advanced.
        if em.status == "at_scene":
            validate_emergency_transition(em.status, "patient_on_board")
            em.status = "patient_on_board"
        validate_emergency_transition(em.status, "hospital_selecting")
        em.status = "hospital_selecting"
        em.version += 1

    await db.flush()

    # technical.md Section12.3: a new hospital request should notify hospital
    # staff both over WS (primary) and push (wakes a backgrounded tab). This
    # function never emitted ANY event for hospital staff before -- found by
    # searching for an outbox.emit call here and finding none at all, not
    # even the WS one push is supposed to merely supplement.
    from app.db.repos import identity as identity_repo
    from app.integrations.push.sender import send_push
    from app.realtime.outbox import emit as outbox_emit_real

    await outbox_emit_real(db, channel=f"hospital:{hospital_id}", event="hospital_request.new", data={
        "hospital_request_id": str(req.id), "emergency_id": str(emergency_id),
        "rank": rank, "score": score, "is_family_choice": is_family_choice,
    })
    for staff_user_id in await identity_repo.get_user_ids_by_hospital_id(db, str(hospital_id)):
        try:
            await send_push(staff_user_id, "New incoming patient",
                             "A new hospital request needs a response.", data={
                                 "hospital_request_id": str(req.id), "emergency_id": str(emergency_id),
                             })
        except Exception:
            import logging
            logging.getLogger("reservations").exception(
                "send_push failed for hospital staff user %s (request %s)", staff_user_id, req.id)

    return req

async def accept_hospital_request(
    db: AsyncSession, request_id: UUID, room_id: UUID | None, staff_ids: list[UUID],
    responder_id: UUID
) -> None:
    req = await db.get(HospitalRequest, request_id)
    if not req: return
    req.status = "accepted"
    req.responded_at = datetime.utcnow()
    req.responder_id = responder_id
    
    if req.reservation_id:
        res = await db.get(Reservation, req.reservation_id)
        if res:
            from app.domain.fsm.reservation_fsm import validate_transition as validate_reservation_transition
            validate_reservation_transition(res.status, "confirmed")
            res.status = "confirmed"
            if room_id:
                res.room_id = room_id

    em = await db.get(Emergency, req.emergency_id)
    if em:
        validate_emergency_transition(em.status, "hospital_confirmed")
        em.status = "hospital_confirmed"
        # em.hospital_id/hospital_confirmed_at were never set here -- the
        # hospital dashboard's "Incoming"/"at_door" lists filter on
        # emergencies.hospital_id, so an accepted request was invisible to
        # the very hospital that just accepted it. Found by checking why a
        # confirmed request still showed "No confirmed ambulances on the way".
        em.hospital_id = req.hospital_id
        em.hospital_confirmed_at = datetime.utcnow()
        em.version += 1

async def reject_hospital_request(
    db: AsyncSession, request_id: UUID, reason_code: str, note: str | None, responder_id: UUID
) -> None:
    req = await db.get(HospitalRequest, request_id)
    if not req: return
    req.status = "rejected"
    req.rejection_reason = reason_code
    req.rejection_note = note
    req.responded_at = datetime.utcnow()
    req.responder_id = responder_id
    
    if req.reservation_id:
        await release_reservation(db, req.reservation_id, "released")

async def timeout_hospital_request(db: AsyncSession, request_id: UUID) -> None:
    req = await db.get(HospitalRequest, request_id)
    if not req: return
    req.status = "rejected"
    req.rejection_reason = "timeout"
    
    if req.reservation_id:
        await release_reservation(db, req.reservation_id, "released")

async def walk_in_override(
    db: AsyncSession,
    room_id: UUID,
    override_reason: str,
    emergency_id_for_reservation: UUID,
    hospital_id: UUID,
    outbox_emit,
) -> dict:
    # 1. Room -> occupied
    room = await db.get(Room, room_id)
    if room:
        room.status = 'occupied'
        room.override_reason = override_reason
        room.version += 1

    # find reservation
    stmt = update(Reservation).where(
        Reservation.emergency_id == emergency_id_for_reservation,
        Reservation.room_id == room_id
    ).values(status='overridden', room_id=None).returning(Reservation)
    res_result = await db.execute(stmt)
    res = res_result.scalar_one_or_none()

    if res:
        await outbox_emit(db, "reservation.overridden", str(res.id), {"reason": override_reason})

    # 2. SAME TRANSACTION: try to find another free acceptable room of the
    # SAME type the overridden room was (not the room's literal `type`
    # string treated as if it were a facility -- that bug meant this never
    # found anything either, same root cause as create_hospital_request_with_hold).
    acceptable_types = [room.type] if room else ["er_bed"]
    new_room = await lock_free_room_skip_locked(db, hospital_id, acceptable_types)

    if new_room:
        # Re-create reservation as confirmed
        new_res = await create_reservation(
            db,
            hospital_id=hospital_id,
            emergency_id=emergency_id_for_reservation,
            status="confirmed",
            room_id=new_room.id,
            hold_expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        await db.execute(
            update(Room).where(Room.id == new_room.id, Room.status == "free")
            .values(status="reserved", reservation_id=new_res.id, version=Room.version + 1)
        )
        await outbox_emit(db, "reservation.changed", str(new_res.id), {"new_room_id": str(new_room.id)})
        return {"re_allocated": True, "new_room_id": new_room.id, "rerouted": False}
    else:
        # start new selection with is_priority=True
        # Need redis/ml client, assuming start_selection can be called here or handled outside
        # we'll emit the event to trigger it
        await outbox_emit(db, "emergency.reroute_required", str(emergency_id_for_reservation), {"reason": "walk_in_override"})
        return {"re_allocated": False, "new_room_id": None, "rerouted": True}
