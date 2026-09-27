"""A provides to B (work-distribution.md §4.1). Real implementation of
technical.md §10.4: writes the outbox row in the SAME transaction as the
caller's state change (caller commits) with a per-channel monotonic `seq`
(technical.md §8). The relay (realtime/relay.py) polls unsent rows, publishes
to Redis pub/sub, and marks them sent -- so a rolled-back transaction never
produces a WS event, and a committed one is never lost even if the relay was
briefly down."""

import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("outbox")


async def emit(session: AsyncSession, *, channel: str, event: str, data: dict) -> None:
    seq = (await session.execute(
        text(
            "INSERT INTO channel_seq (channel, next_seq) VALUES (:channel, 2) "
            "ON CONFLICT (channel) DO UPDATE SET next_seq = channel_seq.next_seq + 1 "
            "RETURNING next_seq - 1"
        ),
        {"channel": channel},
    )).scalar_one()

    await session.execute(
        text(
            "INSERT INTO outbox (channel, event, seq, data) "
            "VALUES (:channel, :event, :seq, CAST(:data AS jsonb))"
        ),
        {"channel": channel, "event": event, "seq": seq, "data": json.dumps(data, default=str)},
    )
    logger.debug("outbox.emit channel=%s event=%s seq=%s", channel, event, seq)
