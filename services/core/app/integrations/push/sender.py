"""A provides to B (work-distribution.md §4.1). Real body: technical.md §12.3 --
Firebase Cloud Messaging web push. Needs FCM_PROJECT_ID / FCM_SERVICE_ACCOUNT_JSON
(infra/env/.env.example) -- stub logs and returns so callers can integrate
before those credentials exist."""

import logging
from uuid import UUID

logger = logging.getLogger("push")


async def send_push(user_id: UUID, title: str, body: str, data: dict) -> None:
    logger.info("send_push (stub) user_id=%s title=%r body=%r data=%s", user_id, title, body, data)
