"""A's file (work-distribution.md §2.2). POST /ambulance/offers/{id}/accept
(technical.md §7.4, §11.1)."""

from fastapi import APIRouter, Depends, HTTPException

from app.db.repos import dispatch as dispatch_repo
from app.db.session import get_session
from app.domain import audit
from app.realtime import outbox
from app.security.deps import CurrentUser, require_role

router = APIRouter()


@router.post("/offers/{offer_id}/accept")
async def accept_offer(offer_id: str, user: CurrentUser = Depends(require_role("paramedic"))) -> dict:
    if not user.ambulance_id:
        raise HTTPException(403, "user has no assigned ambulance")

    async with get_session() as session:
        try:
            result = await dispatch_repo.accept_offer(
                session, offer_id=offer_id, paramedic_ambulance_id=user.ambulance_id,
            )
        except dispatch_repo.OfferNotAvailable:
            await session.rollback()
            raise HTTPException(409, detail={"error": {"code": "ALREADY_TAKEN", "message": "Offer no longer available", "details": {}}})
        except dispatch_repo.AlreadyTaken:
            await session.rollback()
            raise HTTPException(409, detail={"error": {"code": "ALREADY_TAKEN", "message": "Emergency already assigned", "details": {}}})
        except dispatch_repo.AmbulanceBusy:
            await session.rollback()
            raise HTTPException(409, detail={"error": {"code": "ALREADY_TAKEN", "message": "Ambulance no longer available", "details": {}}})

        await audit.write(
            session, actor_type="user", actor_id=str(user.id), entity="emergencies",
            entity_id=result["emergency_id"], action="offer_accepted",
            before=None, after={"ambulance_id": result["ambulance_id"]},
        )
        await outbox.emit(session, channel=f"emergency:{result['emergency_id']}", event="emergency.status",
                           data={"status": "ambulance_assigned"})
        await session.commit()

    return {"emergency_id": result["emergency_id"], "ambulance_id": result["ambulance_id"]}
