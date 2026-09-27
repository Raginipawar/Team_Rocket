"""A provides to B (work-distribution.md §4.1). Real body: technical.md §12.1 --
textbee/httpSMS behind one interface, throttled to respect carrier limits.
Needs SMS_API_KEY / SMS_PROVIDER / SMS_GATEWAY_NUMBER (infra/env/.env.example)
-- stub logs and returns a fake message id so callers can integrate before
those secrets exist."""

import logging
import uuid
from uuid import UUID

logger = logging.getLogger("sms")


async def send_sms(phone: str, body: str, *, emergency_id: UUID | None = None,
                    template: str | None = None) -> str:
    message_id = str(uuid.uuid4())
    logger.info("send_sms (stub) to=%s template=%s emergency_id=%s body=%r message_id=%s",
                phone, template, emergency_id, body, message_id)
    return message_id
