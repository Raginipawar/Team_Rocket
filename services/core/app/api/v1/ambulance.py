"""A's file (work-distribution.md §2.2). technical.md §7.4."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db.session import get_session
from app.domain import dispatch, lifecycle
from app.security.deps import CurrentUser, require_role

router = APIRouter()


class HeartbeatRequest(BaseModel):
    lat: float
    lng: float
    heading: float | None = None
    speed_kmh: float | None = None
    accuracy_m: float | None = None
    client_ts: str | None = None


class StatusRequest(BaseModel):
    status: str  # available | offline | cleaning_done
    version: int


@router.post("/heartbeat", status_code=204)
async def heartbeat(req: HeartbeatRequest, user: CurrentUser = Depends(require_role("paramedic"))) -> None:
    if not user.ambulance_id:
        raise HTTPException(403, "user has no assigned ambulance")
    async with get_session() as session:
        await lifecycle.record_heartbeat(
            session, ambulance_id=user.ambulance_id, lat=req.lat, lng=req.lng,
            heading=req.heading, speed_kmh=req.speed_kmh,
        )
        await session.commit()


@router.post("/status")
async def set_status(req: StatusRequest, user: CurrentUser = Depends(require_role("paramedic"))) -> dict:
    if not user.ambulance_id:
        raise HTTPException(403, "user has no assigned ambulance")
    if req.status not in ("available", "offline", "cleaning_done"):
        raise HTTPException(400, "invalid status")

    async with get_session() as session:
        try:
            result = await lifecycle.set_ambulance_status(
                session, ambulance_id=user.ambulance_id, new_status=req.status, expected_version=req.version,
            )
        except lifecycle.VersionConflict:
            await session.rollback()
            raise HTTPException(409, detail={"error": {"code": "VERSION_CONFLICT", "message": "Ambulance was modified", "details": {}}})
        await session.commit()
    return result


@router.post("/vehicle-issue", status_code=204)
async def vehicle_issue(user: CurrentUser = Depends(require_role("paramedic"))) -> None:
    if not user.ambulance_id:
        raise HTTPException(403, "user has no assigned ambulance")
    async with get_session() as session:
        await dispatch.handle_vehicle_issue(session, ambulance_id=user.ambulance_id)
        await session.commit()
