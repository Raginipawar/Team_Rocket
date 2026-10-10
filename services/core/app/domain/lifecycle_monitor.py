"""Idle/wrong-way ambulance detection + signal weak/lost (technical.md
Section11.10): neither existed anywhere before this. record_heartbeat()
(lifecycle.py) only reacts to a heartbeat actually arriving -- nothing
noticed when heartbeats STOP arriving, or when they keep arriving but the
ambulance stops making real progress toward its target (stuck in traffic,
going the wrong way, or the driver's phone died mid-route).

Same "simple asyncio loop, B's real job framework will eventually own the
scheduling" pattern as realtime/relay.py -- started from main.py's lifespan
alongside it. Per-ambulance progress/signal state is kept in-process (not
Redis) as a documented simplification: it resets on a restart, which just
means detection re-baselines rather than alerting on stale state.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import audit
from app.realtime import outbox

logger = logging.getLogger("lifecycle_monitor")

POLL_INTERVAL_S = 15

SIGNAL_WEAK_SEC = 30
SIGNAL_LOST_SEC = 120

IDLE_ALERT_SEC = 90
IDLE_REDISPATCH_SEC = 150
MIN_PROGRESS_M = 20  # a real step forward, not GPS jitter

OFFLOAD_DELAY_ALERT_MIN = 15

# ambulance_id -> {"last_distance_m": float, "last_progress_at": float (loop time),
#                  "idle_alerted": bool, "idle_redispatched": bool, "signal_state": str}
_progress_state: dict[str, dict] = {}

# emergency_ids already alerted for offload delay, so a 15s poll doesn't
# re-emit the same alert every cycle until the patient is actually offloaded
_offload_alerted: set[str] = set()


def _now_s() -> float:
    return asyncio.get_event_loop().time()


async def _fetch_en_route_ambulances(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(
        text(
            "SELECT a.id AS ambulance_id, a.status AS ambulance_status, "
            "a.last_heartbeat_at, a.heading, a.speed_kmh, "
            "ST_Y(a.current_location::geometry) AS lat, ST_X(a.current_location::geometry) AS lng, "
            "e.id AS emergency_id, e.status AS emergency_status, "
            "ST_Distance(a.current_location, e.location::geography) AS dist_to_pickup_m, "
            "ST_Distance(a.current_location, h.location::geography) AS dist_to_hospital_m "
            "FROM ambulances a "
            "JOIN emergencies e ON e.id = a.active_emergency_id "
            "LEFT JOIN hospitals h ON h.id = e.hospital_id "
            "WHERE e.status IN ('ambulance_assigned', 'patient_on_board') "
            "AND a.current_location IS NOT NULL"
        )
    )).mappings().all()
    return [dict(r) for r in rows]


async def check_signal_health(session: AsyncSession, rows: list[dict]) -> None:
    now = datetime.now(timezone.utc)
    for row in rows:
        ambulance_id = str(row["ambulance_id"])
        last_hb = row["last_heartbeat_at"]
        if last_hb is None:
            continue
        seconds_since = (now - last_hb).total_seconds()
        state = _progress_state.setdefault(ambulance_id, {"signal_state": "ok"})

        if seconds_since >= SIGNAL_LOST_SEC:
            new_state = "lost"
        elif seconds_since >= SIGNAL_WEAK_SEC:
            new_state = "weak"
        else:
            new_state = "ok"

        if new_state == state["signal_state"]:
            continue  # only emit on transition, not every poll

        state["signal_state"] = new_state
        payload = {"ambulance_id": ambulance_id, "emergency_id": str(row["emergency_id"]),
                   "signal": new_state, "seconds_since_heartbeat": round(seconds_since)}

        if new_state == "lost" and row["heading"] is not None and row["speed_kmh"] is not None and row["lat"] is not None:
            # Dead reckoning (technical.md Section11.10): extrapolate along
            # the last known heading/speed rather than let the map marker
            # freeze. This is NOT written back to ambulances.current_location
            # -- that stays the last real GPS fix, so a resumed heartbeat
            # isn't overwritten by a guess. The estimate rides in the event
            # payload only, for the map to render as a dashed "estimated"
            # marker.
            dist_km = (row["speed_kmh"] * seconds_since) / 3600.0
            import math
            heading_rad = math.radians(row["heading"])
            dlat = (dist_km / 111.0) * math.cos(heading_rad)
            dlng = (dist_km / (111.0 * max(math.cos(math.radians(row["lat"])), 0.01))) * math.sin(heading_rad)
            payload["estimated_lat"] = row["lat"] + dlat
            payload["estimated_lng"] = row["lng"] + dlng

        await audit.write(session, actor_type="system", actor_id="lifecycle_monitor", entity="ambulances",
                           entity_id=ambulance_id, action=f"signal_{new_state}", before=None, after=payload)
        await outbox.emit(session, channel=f"ambulance:{ambulance_id}", event="ambulance.signal", data=payload)
        logger.info("ambulance %s signal -> %s (%.0fs since heartbeat)", ambulance_id, new_state, seconds_since)


async def check_idle_progress(session: AsyncSession, rows: list[dict]) -> None:
    from app.domain.dispatch import redispatch_to_point, start_dispatch

    now = _now_s()
    seen_ids = set()
    for row in rows:
        ambulance_id = str(row["ambulance_id"])
        emergency_id = str(row["emergency_id"])
        seen_ids.add(ambulance_id)

        target_dist_m = (row["dist_to_pickup_m"] if row["emergency_status"] == "ambulance_assigned"
                          else row["dist_to_hospital_m"])
        if target_dist_m is None:
            continue

        state = _progress_state.setdefault(ambulance_id, {})
        if "last_distance_m" not in state:
            state.update(last_distance_m=target_dist_m, last_progress_at=now,
                          idle_alerted=False, idle_redispatched=False)
            continue

        if state["last_distance_m"] - target_dist_m >= MIN_PROGRESS_M:
            # real forward progress -- reset the idle clock
            state.update(last_distance_m=target_dist_m, last_progress_at=now,
                          idle_alerted=False, idle_redispatched=False)
            continue

        idle_sec = now - state["last_progress_at"]

        if idle_sec >= IDLE_REDISPATCH_SEC and not state.get("idle_redispatched"):
            state["idle_redispatched"] = True
            logger.warning("ambulance %s idle %.0fs on emergency %s -- redispatching", ambulance_id, idle_sec, emergency_id)
            await outbox.emit(session, channel=f"emergency:{emergency_id}", event="alert", data={
                "kind": "idle_timeout", "message": "Assigned ambulance made no progress for 150s; redispatching.",
            })
            if row["emergency_status"] == "patient_on_board" and row["lat"] is not None:
                # Patient already picked up -- redispatch targets the stuck
                # ambulance's own current location, same as a confirmed
                # breakdown (handle_vehicle_issue), so the replacement picks
                # the patient up from where they actually are.
                await redispatch_to_point(session, emergency_id=emergency_id, lat=row["lat"], lng=row["lng"],
                                           reason="idle_timeout", broken_ambulance_id=ambulance_id)
            else:
                # Patient not yet picked up -- simplification, documented
                # honestly: technical.md Section11.10 asks for a PARALLEL
                # dispatch round that only supersedes the original once a
                # backup accepts. The existing dispatch model (one
                # ambulance_id per emergency) has no "two live assignments"
                # concept to build that on without a larger data-model
                # change, so this instead supersedes immediately and
                # re-dispatches with priority -- same mechanism
                # handle_vehicle_issue already uses for a confirmed
                # breakdown. A real parallel-hold would need emergencies to
                # support more than one concurrent ambulance_id candidate.
                await session.execute(
                    text("UPDATE emergencies SET status='dispatching', ambulance_id=NULL, version=version+1 WHERE id=:id"),
                    {"id": emergency_id},
                )
                await start_dispatch(session, emergency_id=emergency_id, priority=True, reason="idle_timeout")

        elif idle_sec >= IDLE_ALERT_SEC and not state.get("idle_alerted"):
            state["idle_alerted"] = True
            logger.warning("ambulance %s idle %.0fs on emergency %s", ambulance_id, idle_sec, emergency_id)
            await audit.write(session, actor_type="system", actor_id="lifecycle_monitor", entity="ambulances",
                               entity_id=ambulance_id, action="idle_alert", before=None,
                               after={"idle_seconds": round(idle_sec), "emergency_id": emergency_id})
            await outbox.emit(session, channel=f"ambulance:{ambulance_id}", event="ambulance.idle", data={
                "ambulance_id": ambulance_id, "emergency_id": emergency_id, "idle_seconds": round(idle_sec),
            })

    # an ambulance no longer en route (delivered, cancelled, etc.) -- drop
    # its tracked state so it doesn't leak across future assignments
    for stale_id in set(_progress_state) - seen_ids:
        _progress_state.pop(stale_id, None)


async def check_offload_delay(session: AsyncSession) -> None:
    """technical.md's OFFLOAD_DELAY_ALERT_MIN (15 min): the gap between an
    ambulance arriving at a hospital (handoffs.arrived_at) and the patient
    actually being marked received (handoffs.offloaded_at, written by
    domain.handoff.record_patient_received) had no check anywhere -- an
    ambulance could sit outside a hospital for an hour with nothing flagged.
    offload_delay_sec is a real generated column (0001_init.sql) once
    offloaded_at is set, so this only needs to watch the still-waiting rows."""
    rows = (await session.execute(
        text(
            "SELECT emergency_id, hospital_id, "
            "EXTRACT(EPOCH FROM (now() - arrived_at))::int AS waiting_sec "
            "FROM handoffs "
            "WHERE arrived_at IS NOT NULL AND offloaded_at IS NULL "
            "AND now() - arrived_at > interval '1 minute' * :threshold_min"
        ),
        {"threshold_min": OFFLOAD_DELAY_ALERT_MIN},
    )).mappings().all()

    for row in rows:
        emergency_id = str(row["emergency_id"])
        if emergency_id in _offload_alerted:
            continue
        _offload_alerted.add(emergency_id)
        logger.warning("offload delay: emergency %s waiting %ss at hospital %s",
                        emergency_id, row["waiting_sec"], row["hospital_id"])
        await audit.write(session, actor_type="system", actor_id="lifecycle_monitor", entity="emergencies",
                           entity_id=emergency_id, action="offload_delay_alert", before=None,
                           after={"waiting_sec": row["waiting_sec"], "hospital_id": str(row["hospital_id"])})
        await outbox.emit(session, channel=f"hospital:{row['hospital_id']}", event="alert", data={
            "kind": "offload_delay", "emergency_id": emergency_id, "waiting_sec": row["waiting_sec"],
            "message": f"Patient waiting {row['waiting_sec'] // 60} min to be received.",
        })

    # patient was offloaded (or the handoff row is otherwise resolved) --
    # allow a future, different delay on this id to alert again
    still_waiting_ids = {str(r["emergency_id"]) for r in rows}
    _offload_alerted.intersection_update(still_waiting_ids)


async def check_ambulances_once(session: AsyncSession) -> int:
    rows = await _fetch_en_route_ambulances(session)
    await check_signal_health(session, rows)
    await check_idle_progress(session, rows)
    await check_offload_delay(session)
    return len(rows)


async def run_lifecycle_monitor_forever(session_factory) -> None:
    logger.info("lifecycle monitor started, polling every %ss", POLL_INTERVAL_S)
    while True:
        try:
            async with session_factory() as session:
                await check_ambulances_once(session)
                await session.commit()
        except Exception:
            logger.exception("lifecycle monitor iteration failed -- continuing")
        await asyncio.sleep(POLL_INTERVAL_S)
