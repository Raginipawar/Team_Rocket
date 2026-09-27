"""Outbox relay (technical.md §10.4): polls `outbox` for unsent rows, publishes
each to Redis channel `ws:{channel}` as the envelope the WS contract (§8)
defines, then marks it sent. Runs as a background task; B's real job
framework (app/jobs/worker.py) will eventually own the scheduling of this --
for now it's a simple asyncio loop callable directly."""

import asyncio
import json
import logging
import os

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("outbox-relay")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
POLL_INTERVAL_S = 0.5
BATCH_SIZE = 100


async def relay_once(session: AsyncSession, redis_client: redis.Redis) -> int:
    rows = (await session.execute(
        text(
            "SELECT id, channel, event, seq, data, created_at FROM outbox "
            "WHERE sent_at IS NULL ORDER BY id LIMIT :limit"
        ),
        {"limit": BATCH_SIZE},
    )).mappings().all()

    if not rows:
        return 0

    for row in rows:
        envelope = {
            "event": row["event"],
            "channel": row["channel"],
            "seq": row["seq"],
            "ts": row["created_at"].isoformat(),
            "data": row["data"],
        }
        await redis_client.publish(f"ws:{row['channel']}", json.dumps(envelope))

    ids = [row["id"] for row in rows]
    await session.execute(
        text("UPDATE outbox SET sent_at = now() WHERE id = ANY(:ids)"),
        {"ids": ids},
    )
    await session.commit()
    return len(rows)


async def run_relay_forever(session_factory) -> None:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    logger.info("outbox relay started, polling every %ss", POLL_INTERVAL_S)
    try:
        while True:
            async with session_factory() as session:
                sent = await relay_once(session, redis_client)
            await asyncio.sleep(POLL_INTERVAL_S if sent == 0 else 0)
    finally:
        await redis_client.aclose()
