"""Real push notifications via FCM's HTTP v1 API, called directly with
httpx + a hand-signed service-account JWT -- not the firebase-admin SDK.
firebase-admin pulls in google-cloud-firestore/storage and pins exact
pyjwt/httpx versions that collided with what this app already pins (tried
it earlier this session, reverted after cascading conflicts). HTTP v1 needs
only an RS256-signed JWT (pyjwt + cryptography, already real deps here) to
get an OAuth2 access token, then a plain POST per message -- no SDK."""

import json
import logging
import time
from pathlib import Path
from uuid import UUID

import httpx
import jwt

logger = logging.getLogger("push")

SERVICE_ACCOUNT_PATH = Path(__file__).parent.parent.parent.parent.parent.parent / "infra" / "env" / "secrets" / "firebase-service-account.json"
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TOKEN_URL = "https://oauth2.googleapis.com/token"

_cached_token: str | None = None
_cached_token_exp: float = 0.0


def _load_service_account() -> dict | None:
    if not SERVICE_ACCOUNT_PATH.exists():
        return None
    return json.loads(SERVICE_ACCOUNT_PATH.read_text(encoding="utf-8"))


async def _get_access_token(sa: dict) -> str:
    global _cached_token, _cached_token_exp
    now = time.time()
    if _cached_token and now < _cached_token_exp - 60:
        return _cached_token

    # Google's OAuth2 JWT-bearer flow (RFC 7523): sign a short-lived
    # assertion with the service account's own private key, trade it for a
    # real access token. No google-auth library needed -- this is the whole
    # protocol in ~10 lines.
    iat = int(now)
    assertion = jwt.encode(
        {
            "iss": sa["client_email"], "scope": FCM_SCOPE, "aud": TOKEN_URL,
            "iat": iat, "exp": iat + 3600,
        },
        sa["private_key"], algorithm="RS256",
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(TOKEN_URL, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion,
        })
        resp.raise_for_status()
        data = resp.json()

    _cached_token = data["access_token"]
    _cached_token_exp = now + data.get("expires_in", 3600)
    return _cached_token


async def send_push(user_id: UUID, title: str, body: str, data: dict) -> None:
    sa = _load_service_account()
    if sa is None:
        logger.info("send_push (no service account -- stub) user_id=%s title=%r", user_id, title)
        return

    from app.db.repos.push_subscriptions import get_fcm_tokens_for_user
    from app.db.session import get_session

    async with get_session() as session:
        tokens = await get_fcm_tokens_for_user(session, str(user_id))

    if not tokens:
        logger.info("send_push: no FCM tokens registered for user_id=%s", user_id)
        return

    access_token = await _get_access_token(sa)
    url = f"https://fcm.googleapis.com/v1/projects/{sa['project_id']}/messages:send"
    headers = {"Authorization": f"Bearer {access_token}", "content-type": "application/json"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        for token in tokens:
            message = {
                "message": {
                    "token": token,
                    "notification": {"title": title, "body": body},
                    "data": {k: str(v) for k, v in data.items()},
                    # webpush fields matter for a PWA with the tab closed/
                    # backgrounded -- without them some browsers silently
                    # drop a data-only message instead of showing it.
                    "webpush": {"notification": {"title": title, "body": body, "icon": "/icons/icon-192.png"}},
                }
            }
            try:
                resp = await client.post(url, headers=headers, json=message)
                if resp.status_code == 404 or (resp.status_code == 400 and "UNREGISTERED" in resp.text):
                    # Stale token (uninstalled app, cleared storage, etc.) --
                    # expected over time, not an error worth logging loudly.
                    from app.db.repos.push_subscriptions import delete_fcm_token
                    async with get_session() as session2:
                        await delete_fcm_token(session2, token)
                        await session2.commit()
                    continue
                resp.raise_for_status()
            except httpx.HTTPError:
                logger.exception("send_push failed for user_id=%s token=%s...", user_id, token[:12])
