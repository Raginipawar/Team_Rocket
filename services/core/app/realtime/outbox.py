"""A provides to B (work-distribution.md §4.1). Real body: technical.md §10.4 --
insert into the `outbox` table in the SAME transaction as the state change
(`session` must be the active SQLAlchemy AsyncSession), then the relay
publishes to Redis channel ws:{channel}. Needs B's DB models/migrations, not
yet built -- stub logs and returns so B can call it today and integrate for
real once the outbox table exists."""

import logging

logger = logging.getLogger("outbox")


async def emit(session, *, channel: str, event: str, data: dict) -> None:
    logger.info("outbox.emit (stub) channel=%s event=%s data=%s", channel, event, data)
