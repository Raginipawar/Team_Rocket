"""A's file (work-distribution.md §2.2). Heartbeats + geofencing (technical.md
§11.9). Redis GEO write is skipped for now (Postgres ST_DWithin already
answers "nearby ambulances" for dispatch; Redis GEO would only be a caching
optimization on top) -- documented simplification, not a silent gap.
Postgres throttling (technical.md §4: every 15s) is also skipped for now;
every heartbeat writes -- fine at hackathon scale, worth revisiting under load."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repos import ambulances as ambulances_repo
from app.domain import audit, handoff
from app.realtime import outbox

GEOFENCE_SCENE_M = 75
GEOFENCE_HOSPITAL_M = 150


async def record_heartbeat(
    session: AsyncSession, *, ambulance_id: str, lat: float, lng: float,
    heading: float | None, speed_kmh: float | None,
) -> None:
    await session.execute(
        text(
            "UPDATE ambulances SET current_location = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326), "
            "heading = :heading, speed_kmh = :speed_kmh, last_heartbeat_at = now() "
            "WHERE id = :id"
        ),
        {"lat": lat, "lng": lng, "heading": heading, "speed_kmh": speed_kmh, "id": ambulance_id},
    )

    ambulance = await ambulances_repo.get_ambulance(session, ambulance_id)
    if ambulance is None or ambulance.get("active_emergency_id") is None:
        return

    emergency_id = str(ambulance["active_emergency_id"])
    row = (await session.execute(
        text(
            "SELECT status, "
            "ST_Distance(location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS dist_to_pickup_m, "
            "hospital_id "
            "FROM emergencies WHERE id = :id"
        ),
        {"lng": lng, "lat": lat, "id": emergency_id},
    )).mappings().first()
    if row is None:
        return

    if row["status"] == "ambulance_assigned" and row["dist_to_pickup_m"] is not None and row["dist_to_pickup_m"] <= GEOFENCE_SCENE_M:
        await _transition_at_scene(session, emergency_id)

    elif row["status"] == "patient_on_board" and row["hospital_id"] is not None:
        hosp = (await session.execute(
            text(
                "SELECT ST_Distance(location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS dist_m "
                "FROM hospitals WHERE id = :hid"
            ),
            {"lng": lng, "lat": lat, "hid": row["hospital_id"]},
        )).mappings().first()
        if hosp is not None and hosp["dist_m"] <= GEOFENCE_HOSPITAL_M:
            await _transition_arrived_hospital(session, emergency_id)


async def _transition_at_scene(session: AsyncSession, emergency_id: str) -> None:
    result = await session.execute(
        text("UPDATE emergencies SET status='at_scene', at_scene_at=now(), version=version+1 "
             "WHERE id=:id AND status='ambulance_assigned' RETURNING version"),
        {"id": emergency_id},
    )
    if result.rowcount == 0:
        return
    await audit.write(session, actor_type="system", actor_id="geofence", entity="emergencies",
                       entity_id=emergency_id, action="geofence_at_scene", before=None, after={"status": "at_scene"})
    await outbox.emit(session, channel=f"emergency:{emergency_id}", event="emergency.status",
                       data={"status": "at_scene"})


async def _transition_arrived_hospital(session: AsyncSession, emergency_id: str) -> None:
    result = await session.execute(
        text("UPDATE emergencies SET status='arrived_hospital', arrived_hospital_at=now(), version=version+1 "
             "WHERE id=:id AND status='patient_on_board' RETURNING version"),
        {"id": emergency_id},
    )
    if result.rowcount == 0:
        return
    await handoff.ambulance_arrived_hospital(session, emergency_id=emergency_id)
    await audit.write(session, actor_type="system", actor_id="geofence", entity="emergencies",
                       entity_id=emergency_id, action="geofence_arrived_hospital", before=None,
                       after={"status": "arrived_hospital"})
    await outbox.emit(session, channel=f"emergency:{emergency_id}", event="emergency.status",
                       data={"status": "arrived_hospital"})


async def set_ambulance_status(session: AsyncSession, *, ambulance_id: str, new_status: str, expected_version: int) -> dict:
    """technical.md §7.4: POST /ambulance/status {status, version}. cleaning_done
    is a client-facing alias that always resolves to 'available' in storage."""
    stored_status = "available" if new_status == "cleaning_done" else new_status
    result = (await session.execute(
        text(
            "UPDATE ambulances SET status = :status, version = version + 1 "
            "WHERE id = :id AND version = :expected_version "
            "RETURNING id, status, version"
        ),
        {"status": stored_status, "id": ambulance_id, "expected_version": expected_version},
    )).mappings().first()
    if result is None:
        raise VersionConflict()
    return dict(result)


class VersionConflict(Exception):
    pass
