"""DRAFT stub -- real owner is Person B (work-distribution.md §2.2, §11.6
room/staff allocation on accept). A's geofence code (domain/lifecycle.py)
calls ambulance_arrived_hospital's exact signature (work-distribution.md
§4.2) when an ambulance enters the hospital geofence.

record_patient_received was imported by api/v1/hospital.py but never
existed anywhere -- that import alone would crash hospital.py (and so
main.py, once hospital.py is actually mounted) before a single request
could be served. Added here as the same kind of temporary real stand-in
A has written elsewhere for B's not-yet-started pieces: technical.md
§11.9's exact transition list ("received tap by hospital => handed_off,
reservation consumed, room occupied, ambulance -> cleaning"), not a mock."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import audit
from app.realtime import outbox


async def ambulance_arrived_hospital(session: AsyncSession, *, emergency_id: UUID | str) -> None:
    await session.execute(
        text(
            "INSERT INTO handoffs (emergency_id, hospital_id, room_id, arrived_at) "
            "SELECT id, hospital_id, NULL, now() FROM emergencies WHERE id = :id "
            "ON CONFLICT (emergency_id) DO UPDATE SET arrived_at = now()"
        ),
        {"id": str(emergency_id)},
    )


async def record_patient_received(
    session: AsyncSession, *, emergency_id: UUID | str, hospital_id: UUID | str,
    receiving_staff_ids: list, actor_id: UUID | str,
) -> None:
    """technical.md §11.9: hospital's "received" tap. Also used for the
    offload-delay alert (domain/lifecycle_monitor.py): handoffs.offloaded_at
    being set here is exactly what that check watches for."""
    emergency_id = str(emergency_id)

    emergency = (await session.execute(
        text("SELECT ambulance_id, reservation_id FROM emergencies WHERE id = :id"),
        {"id": emergency_id},
    )).mappings().first()
    if emergency is None:
        return

    await session.execute(
        text(
            "UPDATE handoffs SET offloaded_at = now(), receiving_staff_ids = :staff_ids "
            "WHERE emergency_id = :id"
        ),
        {"id": emergency_id, "staff_ids": receiving_staff_ids},
    )
    await session.execute(
        text("UPDATE emergencies SET status = 'handed_off', handed_off_at = now(), version = version + 1 "
             "WHERE id = :id"),
        {"id": emergency_id},
    )
    if emergency["reservation_id"]:
        await session.execute(
            text("UPDATE reservations SET status = 'consumed', version = version + 1 WHERE id = :rid"),
            {"rid": emergency["reservation_id"]},
        )
        await session.execute(
            text("UPDATE rooms SET status = 'occupied', version = version + 1 WHERE reservation_id = :rid"),
            {"rid": emergency["reservation_id"]},
        )
    if emergency["ambulance_id"]:
        await session.execute(
            text("UPDATE ambulances SET status = 'cleaning', version = version + 1 WHERE id = :aid"),
            {"aid": emergency["ambulance_id"]},
        )

    await audit.write(session, actor_type="user", actor_id=str(actor_id), entity="emergencies",
                       entity_id=emergency_id, action="patient_received", before=None,
                       after={"hospital_id": str(hospital_id), "receiving_staff_ids": receiving_staff_ids})
    await outbox.emit(session, channel=f"emergency:{emergency_id}", event="emergency.status",
                       data={"status": "handed_off"})
    try:
        from app.domain.notify import notify_patient_and_family
        await notify_patient_and_family(
            session, emergency_id, "Patient received",
            "The hospital has received the patient and handover is complete.", {"status": "handed_off"},
        )
    except Exception:
        import logging
        logging.getLogger("handoff").exception("notify_patient_and_family failed for emergency %s (handed_off)", emergency_id)
