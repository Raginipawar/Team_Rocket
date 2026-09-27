"""A's file (work-distribution.md §2.2). technical.md §7.3 -- profile,
contacts, push subscriptions."""

from fastapi import APIRouter, Depends

from app.db.repos import push_subscriptions as push_repo
from app.db.session import get_session
from app.security.deps import CurrentUser, require_role

router = APIRouter()


@router.post("/me/push-subscriptions", status_code=204)
async def register_push_subscription(body: dict, user: CurrentUser = Depends(require_role(
    "patient", "paramedic", "hospital_staff", "developer",
))) -> None:
    fcm_token = body["fcm_token"]
    async with get_session() as session:
        await push_repo.add_subscription(session, str(user.id), fcm_token)
        await session.commit()
