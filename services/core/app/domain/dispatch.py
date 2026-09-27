"""A's file (work-distribution.md §2.2). Dispatch round loop (technical.md
§11.1). B's real ETA model (/ml/v1/eta/matrix) doesn't exist yet, so rounds
use a straight-line-distance/assumed-speed placeholder ETA -- swap
`_placeholder_eta_sec` for a call to B's eta capability once it lands, no
other change needed. Round scheduling (+30s) uses asyncio.create_task as a
stand-in for B's real job scheduler (app/jobs/scheduler.py, not built yet)."""

import asyncio
import logging
import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repos import ambulances as ambulances_repo
from app.db.repos import dispatch as dispatch_repo
from app.db.repos import emergencies as emergencies_repo
from app.db.session import get_session
from app.domain import audit, escalation
from app.integrations.ml import dispatch as ml_dispatch
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


async def run_dispatch_round(session: AsyncSession, emergency_id: str, round_num: int) -> str:
    emergency = await emergencies_repo.get_emergency(session, emergency_id)
    if emergency is None or emergency.get("lat") is None:
        logger.warning("dispatch round %s: emergency %s has no location, skipping", round_num, emergency_id)
        return "no_location"

    radius_km = DISPATCH_RADII_KM[round_num - 1]
    exclude_ids = await dispatch_repo.already_offered_ambulance_ids(session, emergency_id)

    candidates = await ambulances_repo.find_candidates(
        session, lat=emergency["lat"], lng=emergency["lng"], radius_km=radius_km,
        required_type=emergency.get("required_ambulance_type") or "BLS",
        exclude_ambulance_ids=exclude_ids,
    )
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
    ranked = await ml_dispatch.dispatch_rank(
        {"location": {"lat": emergency["lat"], "lng": emergency["lng"]},
         "acuity": emergency.get("ai_acuity"), "required_type": emergency.get("required_ambulance_type")},
        ranking_input,
    )

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

    await audit.write(
        session, actor_type="system", actor_id="dispatch", entity="emergencies", entity_id=emergency_id,
        action=f"dispatch_round_{round_num}", before=None, after={"offered_ambulances": [r["ambulance_id"] for r in top]},
    )
    return "offers_created"


async def _continue_rounds(emergency_id: str, next_round: int) -> None:
    for round_num in range(next_round, NO_AMBULANCE_ESCALATE_AFTER_ROUND + 1):
        await asyncio.sleep(DISPATCH_ROUND_INTERVAL_SEC)
        async with get_session() as session:
            emergency = await emergencies_repo.get_emergency(session, emergency_id)
            if emergency is None or emergency["status"] != "dispatching":
                return  # already assigned, cancelled, or otherwise moved on
            await run_dispatch_round(session, emergency_id, round_num)
            await session.commit()

    async with get_session() as session:
        emergency = await emergencies_repo.get_emergency(session, emergency_id)
        if emergency is not None and emergency["status"] == "dispatching":
            await escalation.raise_escalation(
                session, type="no_ambulance", emergency_id=emergency_id,
                context={"summary": f"No ambulance accepted after {NO_AMBULANCE_ESCALATE_AFTER_ROUND} rounds"},
            )
            await session.commit()


async def redispatch_to_point(session: AsyncSession, *, emergency_id, lat: float, lng: float, reason: str) -> None:
    logger.info("redispatch_to_point (stub -- breakdown handling not built yet) emergency_id=%s lat=%s lng=%s reason=%s",
                emergency_id, lat, lng, reason)
