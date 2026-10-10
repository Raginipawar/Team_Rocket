"""A provides to B (work-distribution.md Section4.1). Real body: technical.md
Section12.1 -- textbee/httpSMS behind one interface, throttled to respect
carrier limits, messages split into <=160-char parts, retried with backoff
on transient failure.

Gated by SMS_MODE (infra/env/.env.example): SMS_MODE=fake (default) keeps
the previous honest log-stub behaviour -- no network call, no real SMS,
clearly logged as fake, so nothing pretends to have sent a message it
didn't. SMS_MODE=real requires SMS_PROVIDER (textbee|httpsms), SMS_API_KEY,
and either SMS_GATEWAY_DEVICE_ID (textbee) or SMS_GATEWAY_NUMBER (httpsms)
to be set -- that's the one remaining manual step (an Android phone with a
SIM, running the textbee or httpSMS app, linked to a real account) that
only a human with the hardware in hand can complete; this file is written
so that step is a .env paste, not more code."""

import asyncio
import logging
import uuid
from uuid import UUID

import httpx

from app.config import settings

logger = logging.getLogger("sms")

MAX_PART_LEN = 160
MIN_SECONDS_BETWEEN_SENDS = 2.0  # technical.md Section12.1: outbound throttle <= 1 SMS / 2s
MAX_RETRIES = 3

_last_sent_at = 0.0
_throttle_lock = asyncio.Lock()


def _sms_mode() -> str:
    # settings.SMS_MODE (pydantic-settings' own .env parsing), NOT
    # os.getenv -- pydantic-settings loads .env into the Settings object's
    # fields only, it never touches the real process environment, so
    # os.getenv("SMS_MODE") always saw the "fake" default regardless of
    # what .env said. Confirmed live: a real otp/request logged
    # "SMS_MODE=fake, not sent" even with SMS_MODE=real sitting in .env.
    return settings.SMS_MODE


def _split_parts(body: str) -> list[str]:
    if len(body) <= MAX_PART_LEN:
        return [body]
    return [body[i:i + MAX_PART_LEN] for i in range(0, len(body), MAX_PART_LEN)]


async def _throttle() -> None:
    global _last_sent_at
    async with _throttle_lock:
        now = asyncio.get_event_loop().time()
        wait = MIN_SECONDS_BETWEEN_SENDS - (now - _last_sent_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_sent_at = asyncio.get_event_loop().time()


async def _send_via_textbee(client: httpx.AsyncClient, phone: str, body: str) -> str:
    device_id = settings.SMS_GATEWAY_DEVICE_ID
    resp = await client.post(
        f"https://api.textbee.dev/api/v1/gateway/devices/{device_id}/send-sms",
        headers={"x-api-key": settings.SMS_API_KEY},
        json={"recipients": [phone], "message": body},
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return str((data.get("data") or {}).get("smsBatchId") or data.get("id") or uuid.uuid4())


async def _send_via_httpsms(client: httpx.AsyncClient, phone: str, body: str) -> str:
    resp = await client.post(
        "https://api.httpsms.com/v1/messages/send",
        headers={"x-api-key": settings.SMS_API_KEY},
        json={"content": body, "from": settings.SMS_GATEWAY_NUMBER, "to": phone},
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return str((data.get("data") or {}).get("id") or uuid.uuid4())


async def send_sms(phone: str, body: str, *, emergency_id: UUID | None = None,
                    template: str | None = None) -> str:
    if _sms_mode() != "real":
        message_id = str(uuid.uuid4())
        logger.info("send_sms (SMS_MODE=%s, not sent) to=%s template=%s emergency_id=%s body=%r message_id=%s",
                    settings.SMS_MODE, phone, template, emergency_id, body, message_id)
        return message_id

    provider = settings.SMS_PROVIDER or "textbee"
    sender = _send_via_httpsms if provider == "httpsms" else _send_via_textbee
    required = ("SMS_API_KEY", "SMS_GATEWAY_NUMBER") if provider == "httpsms" else ("SMS_API_KEY", "SMS_GATEWAY_DEVICE_ID")
    missing = [v for v in required if not getattr(settings, v)]
    if missing:
        # A missing credential is a config error, not a transient network
        # failure -- retrying it with backoff would just waste the full
        # 1+2+4s before failing anyway. Fail immediately and say exactly
        # which .env value is missing.
        raise RuntimeError(f"SMS_MODE=real but missing env var(s) for provider={provider}: {missing}")

    last_message_id = ""
    async with httpx.AsyncClient() as client:
        for part in _split_parts(body):
            await _throttle()
            for attempt in range(MAX_RETRIES):
                try:
                    last_message_id = await sender(client, phone, part)
                    logger.info("send_sms OK provider=%s to=%s template=%s emergency_id=%s message_id=%s",
                                provider, phone, template, emergency_id, last_message_id)
                    break
                except httpx.HTTPError as exc:
                    logger.warning("send_sms attempt %s/%s failed provider=%s to=%s: %s",
                                    attempt + 1, MAX_RETRIES, provider, phone, exc)
                    if attempt == MAX_RETRIES - 1:
                        logger.error("send_sms permanently failed provider=%s to=%s template=%s",
                                      provider, phone, template)
                        raise
                    await asyncio.sleep(2 ** attempt)
    return last_message_id
