"""A provides to B (work-distribution.md §4.1). Real body: technical.md §12.3
-- Firebase Cloud Messaging web push. Service account JSON at
infra/env/secrets/firebase-service-account.json (git-ignored, never committed)."""

import logging
from functools import lru_cache
from pathlib import Path
from uuid import UUID

logger = logging.getLogger("push")

SERVICE_ACCOUNT_PATH = Path(__file__).parent.parent.parent.parent.parent.parent / "infra" / "env" / "secrets" / "firebase-service-account.json"


@lru_cache
def _get_app():
    import firebase_admin
    from firebase_admin import credentials

    if not SERVICE_ACCOUNT_PATH.exists():
        return None
    cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
    return firebase_admin.initialize_app(cred)


async def send_push(user_id: UUID, title: str, body: str, data: dict) -> None:
    app = _get_app()
    if app is None:
        logger.info("send_push (no service account -- stub) user_id=%s title=%r", user_id, title)
        return

    from app.db.repos.push_subscriptions import get_fcm_tokens_for_user
    from app.db.session import get_session
    from firebase_admin import messaging

    async with get_session() as session:
        tokens = await get_fcm_tokens_for_user(session, str(user_id))

    if not tokens:
        logger.info("send_push: no FCM tokens registered for user_id=%s", user_id)
        return

    for token in tokens:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in data.items()},
            token=token,
        )
        try:
            messaging.send(message, app=app)
        except Exception:
            logger.exception("send_push failed for user_id=%s token=%s...", user_id, token[:12])
