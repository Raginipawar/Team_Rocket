from typing import List, Optional
import httpx
from app.config import settings

async def send_escalation_alert(escalation, ops_link: str) -> List[int]:
    if not settings.TELEGRAM_BOT_TOKEN:
        print(f"[Telegram Mock] Escalation Alert: {escalation.id} Link: {ops_link}")
        return [1]
        
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    
    text = f"\u26A0\uFE0F <b>ESCALATION</b>: {escalation.escalation_type}\n\n<a href='{ops_link}'>Open Ops Console</a>"
    
    # Inline buttons for options
    inline_keyboard = []
    if escalation.options:
        for opt in escalation.options:
            inline_keyboard.append([{"text": opt.get("label", "Option"), "callback_data": f"esc:{escalation.id}:opt:{opt.get('id')}"}])
    inline_keyboard.append([{"text": "Claim", "callback_data": f"esc:{escalation.id}:claim"}])
            
    payload = {
        "chat_id": settings.TELEGRAM_GROUP_CHAT_ID or "-1",
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": inline_keyboard}
    }
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload, timeout=5.0)
            if r.status_code == 200:
                data = r.json()
                return [data.get("result", {}).get("message_id", 0)]
        except Exception:
            pass
    return []

async def edit_escalation_message(chat_id: int, message_id: int, text: str, keyboard=None) -> None:
    if not settings.TELEGRAM_BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if keyboard: payload["reply_markup"] = keyboard
    async with httpx.AsyncClient() as client:
        try: await client.post(url, json=payload)
        except Exception: pass

async def send_ops_link(chat_id: int, link: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": f"Your Ops Link: {link}"}
    async with httpx.AsyncClient() as client:
        try: await client.post(url, json=payload)
        except Exception: pass

async def send_sms_fallback(phone: str, message: str) -> None:
    print(f"[SMS Fallback Mock] to {phone}: {message}")

async def is_allowed_user(telegram_user_id: int) -> bool:
    return True
