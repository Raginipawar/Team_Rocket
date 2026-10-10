from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.escalation import raise_escalation
from app.domain.reservations import create_hospital_request_with_hold, ACCEPTABLE_ROOM_TYPES
from app.integrations.ml.routing import get_eta, hospital_rank, get_road_comfort, bed_nowcast

FACILITY_TO_CAPABILITY = {
    "cardiac": "cardiac_cathlab", "stroke": "stroke_thrombolysis", "trauma": "trauma_center",
    "burns": "burns_unit", "obstetric": "obstetrics", "pediatric": "pediatrics",
    "poisoning": "toxicology", "respiratory": "icu", "general": "general_er",
}


async def start_selection(
    db: AsyncSession,
    redis,
    ml_client,
    emergency_id: UUID,
    trigger: str,
) -> None:
    """technical.md §11.2. Previous version hardcoded lat/lng=(0.0, 0.0)
    ("# From emergency" -- but never actually read it) and acuity="red"/
    facility="ICU" (neither is a real value in the Acuity/Facility enums),
    so this could never have found real candidates near the real emergency
    or ranked them on real facts -- confirmed by running it, not just
    reading it. Rewritten to read the real emergency row."""
    from app.db.repos.hospitals import list_hospitals_within_km
    from app.db.repos.hospital_requests import list_attempted_hospital_ids
    from app.db.models import Emergency
    from geoalchemy2.shape import to_shape

    em = await db.get(Emergency, emergency_id)
    if em is None or em.location is None:
        await raise_escalation(db, type="no_hospital", emergency_id=emergency_id,
                                context={"trigger": trigger, "reason": "Emergency has no location"})
        return

    point = to_shape(em.location)
    lat, lng = point.y, point.x
    acuity = em.acuity or "urgent"
    facility = em.facility or "general"

    candidates = await list_hospitals_within_km(db, lat, lng, radius_km=25.0)
    # Exclude hospitals already offered this emergency (any status) -- on
    # the very first call this is an empty set (no-op); on a re-run after
    # cancel/reject/timeout it's what stops this from just re-offering the
    # same hospital with nothing changed.
    already_tried = {str(h) for h in await list_attempted_hospital_ids(db, emergency_id)}
    candidates = [c for c in candidates if str(c.id) not in already_tried]
    if not candidates:
        await raise_escalation(db, type="no_hospital", emergency_id=emergency_id,
                                context={"trigger": trigger, "reason": "No candidates within 25km"})
        return

    required_capability = FACILITY_TO_CAPABILITY.get(facility, "general_er")
    candidate_features = []
    candidate_by_id = {}
    for cand in candidates:
        cand_point = to_shape(cand.location)
        eta_data = await get_eta(ml_client, {"lat": lat, "lng": lng}, {"lat": cand_point.y, "lng": cand_point.x}, None)
        comfort = await get_road_comfort(ml_client, "")
        eta_sec = eta_data.get("seconds", 600)
        nowcast = await bed_nowcast(ml_client, str(cand.id), ACCEPTABLE_ROOM_TYPES.get(facility, ["er_bed"])[0],
                                     1, 10, eta_data.get("minutes", 10))

        candidate_by_id[str(cand.id)] = cand
        candidate_features.append({
            "hospital_id": str(cand.id),
            "features": {
                "facility_match": required_capability in (cand.capabilities or []),
                "required_resources_available_prob": nowcast.get("score", 0.5),
                "p_bed_available_at_eta": nowcast.get("score", 0.5),
                "eta_sec": float(eta_sec),
                "eta_high_sec": float(eta_sec) * 1.3,
                "road_comfort": comfort.get("score", 0.5),
                "specialist_on_duty_at_eta": 1.0,  # staff_shifts lookup not wired yet -- optimistic default, documented gap
                "staleness_min": 0.0,
                "occupancy_ratio": 0.5,  # hospital_occupancy_history not wired yet -- neutral default, documented gap
                "rejection_rate_24h": 0.1,
                "incoming_reserved_count": 0,
                "stabilization_capable": cand.stabilization_capable,
                "fragility": "true" if em.fragility else "false",
            },
        })

    emergency_features = {
        "acuity": acuity, "facility": facility,
        "fragility": "true" if em.fragility else "false",
        "required_resources": [],
    }
    ranked = await hospital_rank(ml_client, emergency_features, candidate_features)

    eligible_ranked = [r for r in ranked if r.get("eligible", True)]
    if not eligible_ranked:
        await raise_escalation(db, type="no_hospital", emergency_id=emergency_id,
                                context={"trigger": trigger, "reason": "No eligible hospital after ranking"})
        return

    # Real predicted-resources list (e.g. ["ventilator", "cath_lab"]) instead
    # of create_hospital_request_with_hold's old hardcoded "ventilator" --
    # uses the already-wired ml.resources() wrapper (real call_ml, real base
    # URL/timeout/MLUnavailable handling), not a raw ad-hoc httpx call against
    # `ml_client` treated as a URL string (ml_client is None at every real
    # call site in this codebase, so that pattern always silently fell
    # through to a fallback anyway).
    from app.integrations.ml.intake import resources as ml_resources
    resources_result = await ml_resources(acuity, facility, em.extracted or {})
    required_resources = (
        [r["item"] for r in resources_result.get("resources", []) if r.get("prob", 0) >= 0.7]
        if resources_result else ["ventilator"]
    )

    for candidate in eligible_ranked:
        hospital_id = candidate["hospital_id"]
        try:
            await create_hospital_request_with_hold(
                db, emergency_id=emergency_id, hospital_id=UUID(hospital_id),
                rank=candidate.get("rank", 1), features=candidate.get("features", {}),
                explanation=candidate.get("explanation", []), acuity=acuity, facility=facility,
                score=candidate.get("score"), required_resources=required_resources,
            )
            return
        except Exception:
            continue  # this hospital had no free room/resource -- try the next ranked one

    await raise_escalation(db, type="no_hospital", emergency_id=emergency_id,
                            context={"trigger": trigger, "reason": "All eligible hospitals had no free room/resource"})
