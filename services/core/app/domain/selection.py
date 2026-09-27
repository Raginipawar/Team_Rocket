from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from services.core.app.domain.escalation import raise_escalation
from services.core.app.domain.reservations import create_hospital_request_with_hold
from services.core.app.integrations.ml.routing import get_eta, hospital_rank, get_road_comfort, bed_nowcast

async def start_selection(
    db: AsyncSession,
    redis,
    ml_client,
    emergency_id: UUID,
    trigger: str,
) -> None:
    """
    1. Find candidates within 25km + hard constraints
    2. Get ETA, road_comfort, nowcast, specialist-on-duty, staleness
    3. Call /ml/v1/hospital-rank
    4. Send request to rank 1 via create_hospital_request_with_hold()
    On list exhausted: raise_escalation(no_hospital)
    """
    from services.core.app.db.repos.hospitals import list_hospitals_within_km
    # Mocking location and candidates retrieval logic for now
    lat, lng = 0.0, 0.0 # From emergency
    candidates = await list_hospitals_within_km(db, lat, lng, radius_km=25.0)
    
    if not candidates:
        await raise_escalation(db, "no_hospital", emergency_id, {"trigger": trigger, "reason": "No candidates within 25km"})
        return
        
    candidate_features = []
    for cand in candidates:
        # Mock values, in real implementation we fetch these
        eta_data = await get_eta(ml_client, "origin", "cand", None)
        comfort = await get_road_comfort(ml_client, "geom")
        nowcast = await bed_nowcast(ml_client, str(cand.id), "ICU", 1, 10, eta_data.get("minutes", 10))
        candidate_features.append({
            "id": str(cand.id),
            "eta": eta_data.get("minutes", 10),
            "road_comfort": comfort.get("score", 0.5),
            "nowcast_score": nowcast.get("score", 0.5),
            "specialist": True,
            "staleness": 5
        })
        
    emergency_features = {"id": str(emergency_id), "acuity": "red"}
    ranked = await hospital_rank(ml_client, emergency_features, candidate_features)
    
    if not ranked:
        await raise_escalation(db, "no_hospital", emergency_id, {"trigger": trigger, "reason": "Ranking returned empty"})
        return
        
    top_candidate = ranked[0]
    
    await create_hospital_request_with_hold(
        db,
        emergency_id=emergency_id,
        hospital_id=UUID(top_candidate["id"]),
        rank=1,
        features=top_candidate.get("features", {}),
        explanation=top_candidate.get("explanation", []),
        acuity="red",
        facility="ICU"
    )
