"""Real Telegram webhook (technical.md §13): handles a crew member tapping
"I'm handling this" or an option button on a real escalation alert. Was a
stub that checked the secret against a literal "YOUR_SECRET_TOKEN" string
(so it rejected every real call, including real ones with the right
secret) and did nothing with the payload either way."""

import logging

from fastapi import APIRouter, Header, HTTPException, Request
from typing import Optional

from app.config import settings
from app.db.session import get_session
from app.domain import ops as ops_domain
from app.integrations.telegram.client import edit_escalation_message, is_allowed_user

router = APIRouter(prefix="/webhooks/telegram", tags=["webhooks"])
logger = logging.getLogger("telegram-webhook")


@router.post("")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
    if not settings.TELEGRAM_WEBHOOK_SECRET or x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid token"}})

    data = await request.json()
    cq = data.get("callback_query")
    if not cq:
        return {"status": "ok"}  # message/other update types -- nothing to do yet

    callback_id = cq["id"]
    tg_user_id = cq["from"]["id"]
    message = cq.get("message") or {}
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    action = cq.get("data", "")

    async def _answer(text: str) -> None:
        import httpx
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:  # see telegram/client.py for why
            await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text},
            )

    if not await is_allowed_user(tg_user_id):
        await _answer("Your Telegram account isn't registered as a team member for this.")
        return {"status": "ok"}

    async with get_session() as session:
        from sqlalchemy import text as sql_text
        user_row = (await session.execute(
            sql_text("SELECT id, name FROM users WHERE telegram_user_id = :tid"), {"tid": tg_user_id},
        )).mappings().first()
        if not user_row:
            await _answer("Account not found.")
            return {"status": "ok"}

        if action.startswith("claim:"):
            escalation_id = action.split(":", 1)[1]
            try:
                await ops_domain.claim_escalation(session, escalation_id, user_row["id"])
                await session.commit()
                await _answer("Claimed.")
                await edit_escalation_message(chat_id, message_id, f"✅ Claimed by {user_row['name'] or 'a team member'}")
            except Exception as e:
                await session.rollback()
                logger.warning("claim via telegram failed escalation=%s: %s", escalation_id, e)
                await _answer("Already claimed by someone else.")
        elif action.startswith("opt:"):
            _, escalation_id, option_id = action.split(":", 2)
            from app.db.repos.escalations import AlreadyTaken
            try:
                # resolve_escalation only allows the claimer to resolve
                # (domain/ops.py) -- tapping an option directly, without
                # having tapped "I'm handling this" first, must still work
                # for the common one-tap case, so claim first (no-op if
                # already claimed by this same person).
                try:
                    await ops_domain.claim_escalation(session, escalation_id, user_row["id"])
                except AlreadyTaken:
                    pass
                await ops_domain.resolve_escalation(session, escalation_id, option_id, user_row["id"])
                await session.commit()
                await _answer(f"Resolved: {option_id}")
                await edit_escalation_message(chat_id, message_id, f"✅ Resolved ({option_id}) by {user_row['name'] or 'a team member'}")
            except Exception as e:
                await session.rollback()
                logger.warning("resolve via telegram failed escalation=%s: %s", escalation_id, e)
                await _answer("Could not resolve -- someone else may be handling this.")

    return {"status": "ok"}
