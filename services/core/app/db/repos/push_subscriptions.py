"""A's file (work-distribution.md §2.2). technical.md §7.3 POST /me/push-subscriptions."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def add_subscription(session: AsyncSession, user_id: str, fcm_token: str) -> None:
    await session.execute(
        text("INSERT INTO push_subscriptions (user_id, fcm_token) VALUES (:uid, :token)"),
        {"uid": user_id, "token": fcm_token},
    )


async def get_fcm_tokens_for_user(session: AsyncSession, user_id: str) -> list[str]:
    rows = (await session.execute(
        text("SELECT fcm_token FROM push_subscriptions WHERE user_id = :uid"),
        {"uid": user_id},
    )).scalars().all()
    return list(rows)


async def delete_fcm_token(session: AsyncSession, fcm_token: str) -> None:
    """A token FCM reports as unregistered (app uninstalled, storage
    cleared, etc.) -- stale, must not keep being sent to or counted as a
    working subscription."""
    await session.execute(text("DELETE FROM push_subscriptions WHERE fcm_token = :token"), {"token": fcm_token})
