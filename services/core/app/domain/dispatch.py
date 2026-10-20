"""A's file (work-distribution.md §2.2). Dispatch round loop (technical.md
§11.1). B's real ETA model (/ml/v1/eta/matrix) doesn't exist yet, so rounds
use a straight-line-distance/assumed-speed placeholder ETA -- swap
`_placeholder_eta_sec` for a call to B's eta capability once it lands, no
other change needed. Round scheduling (+30s) uses asyncio.create_task as a
stand-in for B's real job scheduler (app/jobs/scheduler.py, not built yet)."""

import asyncio
import logging
import math

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repos import ambulances as ambulances_repo
from app.db.repos import dispatch as dispatch_repo
from app.db.repos import emergencies as emergencies_repo
from app.db.repos import identity as identity_repo
from app.db.session import get_session
from app.domain import audit, escalation
from app.integrations.ml import dispatch as ml_dispatch
from app.integrations.push.sender import send_push
from app.realtime import outbox

logger = logging.getLogger("dispatch")

DISPATCH_RADII_KM = [5, 10, 20]
OFFERS_PER_ROUND = 4
DISPATCH_ROUND_INTERVAL_SEC = 30
NO_AMBULANCE_ESCALATE_AFTER_ROUND = 3
ASSUMED_SPEED_KMH = 30.0


def _placeholder_eta_sec(distance_m: float) -> int:
    hours = (distance_m / 1000.0) / ASSUMED_SPEED_KMH
    return max(30, round(hours * 3600))


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def start_dispatch(session: AsyncSession, *, emergency_id, priority: bool = False, reason: str) -> None:
    round_result = await run_dispatch_round(session, str(emergency_id), round_num=1)
    if round_result in ("offers_created", "no_candidates"):
        asyncio.create_task(_continue_rounds(str(emergency_id), next_round=2))


async def run_dispatch_round(
    session: AsyncSession, emergency_id: str, round_num: int, *,
    origin_override: tuple[float, float] | None = None,
    extra_excluded_ambulance_ids: list[str] | None = None,
) -> str:
    emergency = await emergencies_repo.get_emergency(session, emergency_id)
    if emergency is None or (emergency.get("lat") is None and origin_override is None):
        logger.warning("dispatch round %s: emergency %s has no location, skipping", round_num, emergency_id)
        return "no_location"

    origin_lat, origin_lng = origin_override or (emergency["lat"], emergency["lng"])
    # With a small fleet, the 5/10/20km expanding-radius search can leave a
    # patient waiting through 1-2 rounds (up to 60s) for literally the only
    # other ambulance in range, or find nothing at all if it happens to sit
    # just past 20km -- there's no real "search wider first" value when
    # there's barely anyone to search among. Below the threshold, skip the
    # radius restriction entirely and go straight to nearest-available,
    # no distance cap.
    total_available = (await session.execute(text(
        "SELECT COUNT(*) FROM ambulances WHERE status = 'available' AND kyc_verified = true"
    ))).scalar_one()
    SMALL_FLEET_THRESHOLD = 3
    radius_km = DISPATCH_RADII_KM[round_num - 1] if total_available > SMALL_FLEET_THRESHOLD else 20000.0
    exclude_ids = await dispatch_repo.already_offered_ambulance_ids(session, emergency_id)
    exclude_ids = list(set(exclude_ids) | set(extra_excluded_ambulance_ids or []))

    # Triage no longer gates dispatch: until it exists, prefer ALS, then fall back to any unit.
    required_type = (emergency.get("required_ambulance_type") if emergency.get("ai_acuity") else None) or "ALS"
    # Clinical-specialty matching (not a ride-hailing distance-only pick): a
    # cardiac/trauma/pediatric case prefers an ambulance actually equipped
    # and crewed for it, when one's genuinely available nearby -- a
    # preference in find_candidates' ordering, never a hard requirement
    # that could leave a critical patient with no ambulance at all.
    required_capability = {
        "cardiac": "cardiac", "trauma": "trauma", "pediatric": "pediatric", "respiratory": "ventilator",
    }.get(emergency.get("ai_facility") or emergency.get("final_facility") or "")

    async def _find(rt: str):
        return await ambulances_repo.find_candidates(
            session, lat=origin_lat, lng=origin_lng, radius_km=radius_km,
            required_type=rt, exclude_ambulance_ids=exclude_ids, required_capability=required_capability,
        )

    candidates = await _find(required_type)
    if not candidates and required_type == "ALS":
        candidates = await _find("BLS")  # find_candidates only filters by type when ALS, so this means "any unit"
    if not candidates:
        logger.info("dispatch round %s for %s: no candidates within %s km", round_num, emergency_id, radius_km)
        return "no_candidates"

    ranking_input = [
        {
            "ambulance_id": str(c["id"]), "type": c["type"],
            "eta_sec": _placeholder_eta_sec(c["distance_m"]), "distance_m": c["distance_m"],
            "hours_on_shift": 0, "mins_since_last_job": 999, "accept_rate_7d": 0.7,
            "avg_accept_latency_s": 8.0, "declines_today": 0,
        }
        for c in candidates
    ]
    try:
        ranked = await asyncio.wait_for(
            ml_dispatch.dispatch_rank(
                {"location": {"lat": origin_lat, "lng": origin_lng},
                 "acuity": emergency.get("ai_acuity"), "required_type": required_type},
                ranking_input,
            ),
            timeout=2.0,
        )
    except Exception:
        logger.warning("dispatch_rank unavailable, falling back to nearest-first")
        ranked = [
            {"ambulance_id": ri["ambulance_id"], "accept_prob": 0.7, "expected_arrival_sec": ri["eta_sec"]}
            for ri in ranking_input
        ]

    top = ranked[:OFFERS_PER_ROUND]
    for i, r in enumerate(top):
        offer = await dispatch_repo.create_offer(
            session, emergency_id=emergency_id, ambulance_id=r["ambulance_id"], round=round_num,
            predicted_accept_prob=r["accept_prob"], predicted_eta_sec=r["expected_arrival_sec"], rank=i + 1,
        )
        await outbox.emit(session, channel=f"ambulance:{r['ambulance_id']}", event="offer.new", data={
            "offer_id": str(offer["id"]), "emergency_id": emergency_id,
            "acuity": emergency.get("ai_acuity"), "eta_sec": r["expected_arrival_sec"],
            "expires_at": offer["expires_at"].isoformat(),
        })
        # technical.md Section12.3: push wakes a backgrounded tab; WS stays
        # primary. send_push() itself was already real (Firebase Admin SDK),
        # but nothing in the whole codebase ever called it for a new offer --
        # found by searching for callers and finding none. Best-effort: a
        # failed push must never fail the dispatch round itself.
        for paramedic_user_id in await identity_repo.get_user_ids_by_ambulance_id(session, r["ambulance_id"]):
            try:
                await send_push(paramedic_user_id, "New emergency offer",
                                 f"ETA {r['expected_arrival_sec'] // 60} min away", data={
                                     "offer_id": str(offer["id"]), "emergency_id": emergency_id,
                                 })
            except Exception:
                logger.exception("send_push failed for paramedic user %s (offer %s)", paramedic_user_id, offer["id"])

    await audit.write(
        session, actor_type="system", actor_id="dispatch", entity="emergencies", entity_id=emergency_id,
        action=f"dispatch_round_{round_num}", before=None, after={"offered_ambulances": [r["ambulance_id"] for r in top]},
    )
    return "offers_created"


async def _continue_rounds(
    emergency_id: str, next_round: int, *,
    origin_override: tuple[float, float] | None = None,
    extra_excluded_ambulance_ids: list[str] | None = None,
) -> None:
    for round_num in range(next_round, NO_AMBULANCE_ESCALATE_AFTER_ROUND + 1):
        await asyncio.sleep(DISPATCH_ROUND_INTERVAL_SEC)
        async with get_session() as session:
            emergency = await emergencies_repo.get_emergency(session, emergency_id)
            if emergency is None or emergency["status"] != "dispatching":
                return  # already assigned, cancelled, or otherwise moved on
            await run_dispatch_round(session, emergency_id, round_num, origin_override=origin_override,
                                      extra_excluded_ambulance_ids=extra_excluded_ambulance_ids)
            await session.commit()

    async with get_session() as session:
        emergency = await emergencies_repo.get_emergency(session, emergency_id)
        if emergency is not None and emergency["status"] == "dispatching":
            await escalation.raise_escalation(
                session, type="no_ambulance", emergency_id=emergency_id,
                context={"summary": f"No ambulance accepted after {NO_AMBULANCE_ESCALATE_AFTER_ROUND} rounds"},
            )
            await session.commit()


async def handle_vehicle_issue(session: AsyncSession, *, ambulance_id: str) -> None:
    """technical.md §11.11: POST /ambulance/vehicle-issue -> ambulance
    out_of_service. If patient not on board, the emergency goes back to
    dispatching as priority. If on board, redispatch to the ambulance's own
    current location (its last known heartbeat), not the original scene."""
    ambulance = await ambulances_repo.get_ambulance(session, ambulance_id)
    if ambulance is None:
        return

    await session.execute(
        text("UPDATE ambulances SET status='out_of_service', version=version+1 WHERE id=:id"),
        {"id": ambulance_id},
    )
    await audit.write(session, actor_type="user", actor_id=ambulance_id, entity="ambulances",
                       entity_id=ambulance_id, action="vehicle_issue", before=None, after={"status": "out_of_service"})

    emergency_id = ambulance.get("active_emergency_id")
    if emergency_id is None:
        return
    emergency_id = str(emergency_id)
    emergency = await emergencies_repo.get_emergency(session, emergency_id)
    if emergency is None:
        return

    if emergency["status"] == "patient_on_board":
        loc = (await session.execute(
            text("SELECT ST_Y(current_location::geometry) AS lat, ST_X(current_location::geometry) AS lng "
                 "FROM ambulances WHERE id = :id"),
            {"id": ambulance_id},
        )).mappings().first()
        if loc and loc["lat"] is not None:
            await redispatch_to_point(session, emergency_id=emergency_id, lat=loc["lat"], lng=loc["lng"],
                                       reason="vehicle_breakdown", broken_ambulance_id=ambulance_id)
    elif emergency["status"] in ("ambulance_assigned", "at_scene"):
        await session.execute(
            text("UPDATE emergencies SET status='dispatching', ambulance_id=NULL, version=version+1 WHERE id=:id"),
            {"id": emergency_id},
        )
        await outbox.emit(session, channel=f"emergency:{emergency_id}", event="alert", data={
            "kind": "breakdown", "message": "Assigned ambulance broke down; re-dispatching.",
        })
        await start_dispatch(session, emergency_id=emergency_id, priority=True, reason="breakdown")


async def redispatch_to_point(
    session: AsyncSession, *, emergency_id, lat: float, lng: float, reason: str,
    broken_ambulance_id: str | None = None,
) -> None:
    """technical.md §11.11: breakdown with patient already on board -- new
    dispatch is targeted at the broken-down ambulance's current location
    (not the original scene), so the replacement ambulance picks the patient
    up from where the old one actually stopped."""
    emergency_id = str(emergency_id)
    await session.execute(
        text("UPDATE emergencies SET status='dispatching', ambulance_id=NULL, version=version+1 WHERE id=:id"),
        {"id": emergency_id},
    )
    await audit.write(
        session, actor_type="system", actor_id="breakdown", entity="emergencies", entity_id=emergency_id,
        action="redispatch_to_point", before=None, after={"lat": lat, "lng": lng, "reason": reason},
    )
    await outbox.emit(session, channel=f"emergency:{emergency_id}", event="reroute", data={
        "from_hospital": None, "to_hospital": None, "reason": reason,
    })

    exclude = [broken_ambulance_id] if broken_ambulance_id else []
    round_result = await run_dispatch_round(
        session, emergency_id, round_num=1, origin_override=(lat, lng), extra_excluded_ambulance_ids=exclude,
    )
    if round_result in ("offers_created", "no_candidates"):
        asyncio.create_task(_continue_rounds(emergency_id, next_round=2, origin_override=(lat, lng),
                                              extra_excluded_ambulance_ids=exclude))
