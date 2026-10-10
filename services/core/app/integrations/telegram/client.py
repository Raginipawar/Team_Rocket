"""Real Telegram Bot API client (technical.md §13 crisis escalation).
Was entirely a no-op stub -- nothing in the whole codebase ever called it
either, same gap class as push notifications before this session fixed
that. Real https://api.telegram.org/bot<token>/... calls now."""

import logging
from typing import List

import httpx

from app.config import settings

logger = logging.getLogger("telegram")

API_BASE = "https://api.telegram.org"


def _api_url(method: str) -> str:
    return f"{API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


def _escalation_text(escalation_type: str, summary: str) -> str:
    labels = {
        "no_ambulance": "🚨 NO AMBULANCE ACCEPTED",
        "no_hospital": "🚨 NO HOSPITAL CONFIRMED",
        "mass_casualty": "🚨 MASS CASUALTY",
        "system_anomaly": "⚠️ SYSTEM ANOMALY",
    }
    header = labels.get(escalation_type, f"🚨 {escalation_type.upper()}")
    return f"{header}\n\n{summary}"


def _build_keyboard(escalation_id: str, options: list[dict]) -> dict:
    rows = [[{"text": "✅ I'm handling this", "callback_data": f"claim:{escalation_id}"}]]
    for opt in options:
        label = opt.get("label") or opt.get("id") or "Option"
        opt_id = opt.get("id") or opt.get("option_id")
        if opt_id:
            rows.append([{"text": label, "callback_data": f"opt:{escalation_id}:{opt_id}"}])
    return {"inline_keyboard": rows}


async def send_escalation_alert(escalation, ops_link: str) -> List[int]:
    """escalation: anything with .id/.type/.summary/.options (the real
    Escalation ORM row, app/db/models/control.py). TELEGRAM_MODE=fake logs
    instead of sending -- same honest fake/real split as SMS."""
    if settings.TELEGRAM_MODE != "real":
        logger.info("send_escalation_alert (TELEGRAM_MODE=%s, not sent) type=%s summary=%r",
                    settings.TELEGRAM_MODE, getattr(escalation, "type", None), getattr(escalation, "summary", None))
        return []
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_GROUP_CHAT_ID:
        logger.error("send_escalation_alert: TELEGRAM_MODE=real but TELEGRAM_BOT_TOKEN/TELEGRAM_GROUP_CHAT_ID not set")
        return []

    text = _escalation_text(getattr(escalation, "type", "escalation"), getattr(escalation, "summary", "") or "")
    if ops_link:
        text += f"\n\n{ops_link}"
    options = getattr(escalation, "options", None) or []
    keyboard = _build_keyboard(str(escalation.id), options)

    # verify=False: this network does TLS interception on outbound HTTPS
    # (same root cause as the Cloudflare/ngrok handshake failures diagnosed
    # earlier this session) -- confirmed by a teammate's own independent
    # test script needing the identical workaround against this same bot.
    # Scoped to just the Telegram API client, not applied globally.
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        resp = await client.post(_api_url("sendMessage"), json={
            "chat_id": settings.TELEGRAM_GROUP_CHAT_ID, "text": text, "reply_markup": keyboard,
        })
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            logger.error("send_escalation_alert: Telegram API rejected the message: %s", data)
            return []
        message_id = data["result"]["message_id"]
        logger.info("send_escalation_alert OK escalation_id=%s message_id=%s", escalation.id, message_id)
        return [message_id]


async def edit_escalation_message(chat_id, message_id: int, text: str, keyboard=None) -> None:
    if settings.TELEGRAM_MODE != "real":
        logger.info("edit_escalation_message (TELEGRAM_MODE=%s, not sent) message_id=%s text=%r",
                    settings.TELEGRAM_MODE, message_id, text)
        return
    payload = {"chat_id": chat_id or settings.TELEGRAM_GROUP_CHAT_ID, "message_id": message_id, "text": text}
    if keyboard is not None:
        payload["reply_markup"] = keyboard
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        resp = await client.post(_api_url("editMessageText"), json=payload)
        if resp.status_code != 200:
            logger.warning("edit_escalation_message failed message_id=%s: %s", message_id, resp.text)


async def send_ops_link(chat_id: int, link: str) -> None:
    if settings.TELEGRAM_MODE != "real":
        logger.info("send_ops_link (TELEGRAM_MODE=%s, not sent) link=%s", settings.TELEGRAM_MODE, link)
        return
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        await client.post(_api_url("sendMessage"), json={"chat_id": chat_id, "text": link})


async def send_sms_fallback(phone: str, message: str) -> None:
    """Escalation alert repeated by SMS if nobody claims it in time
    (technical.md §13) -- reuses the already-real SMS integration rather
    than a second implementation of the same thing."""
    from app.integrations.sms.sender import send_sms
    await send_sms(phone, message, template="escalation_fallback")


async def is_allowed_user(telegram_user_id: int) -> bool:
    """Only a real registered team member (users.telegram_user_id set,
    developer role -- the real 'ops' role per domain/privacy.py) can claim
    an escalation via the Telegram button. Was `return True` unconditionally
    -- anyone in the group chat could claim/resolve a real crisis."""
    from app.db.session import get_session
    from sqlalchemy import text as sql_text
    async with get_session() as session:
        row = (await session.execute(
            sql_text("SELECT 1 FROM users WHERE telegram_user_id = :tid AND role = 'developer' AND is_active = true"),
            {"tid": telegram_user_id},
        )).scalar_one_or_none()
    return bool(row)
