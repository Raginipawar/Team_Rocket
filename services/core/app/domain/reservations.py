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
) -> HospitalRequest:
    room = await lock_free_room_skip_locked(db, hospital_id, [facility])
    resource_ok = await decrement_resource(db, hospital_id, "ventilator", 1)
    
    expires = datetime.utcnow() + timedelta(minutes=5)
    res = await create_reservation(
        db, 
        hospital_id=hospital_id, 
        emergency_id=emergency_id,
        status="held",
        room_id=room.id if room else None,
        expires_at=expires
    )
    
    req = HospitalRequest(
        emergency_id=emergency_id,
        hospital_id=hospital_id,
        reservation_id=res.id,
        status="pending",
        rank=rank,
        is_family_choice=is_family_choice
    )
    db.add(req)
    
    em = await db.get(Emergency, emergency_id)
    if em and em.status != "hospital_selecting":
        em.status = "hospital_selecting"
        em.version += 1
        
    await db.flush()
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
            res.status = "confirmed"
            if room_id:
                res.room_id = room_id
                
    em = await db.get(Emergency, req.emergency_id)
    if em:
        em.status = "hospital_confirmed"
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
        outbox_emit(db, "reservation.overridden", str(res.id), {"reason": override_reason})
    
    # 2. SAME TRANSACTION: try to find another free acceptable room
    facility = room.type if room else "ICU" # fallback
    new_room = await lock_free_room_skip_locked(db, hospital_id, [facility])
    
    if new_room:
        # Re-create reservation as confirmed
        new_res = await create_reservation(
            db, 
            hospital_id=hospital_id, 
            emergency_id=emergency_id_for_reservation,
            status="confirmed",
            room_id=new_room.id,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        outbox_emit(db, "reservation.changed", str(new_res.id), {"new_room_id": str(new_room.id)})
        return {"re_allocated": True, "new_room_id": new_room.id, "rerouted": False}
    else:
        # start new selection with is_priority=True
        # Need redis/ml client, assuming start_selection can be called here or handled outside
        # we'll emit the event to trigger it
        outbox_emit(db, "emergency.reroute_required", str(emergency_id_for_reservation), {"reason": "walk_in_override"})
        return {"re_allocated": False, "new_room_id": None, "rerouted": True}
