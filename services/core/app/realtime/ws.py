"""A's file (work-distribution.md §2.2). WS contract (technical.md §8):
GET /ws?token=<access_jwt> (track_token/ops_session support is a TODO --
access_jwt covers patient/paramedic/hospital_staff/ops-as-developer today).
Client sends {"op":"subscribe","channel":...}; server checks channel
authorization by role, then bridges Redis pub/sub ws:{channel} -> the socket,
applying domain.privacy.project per event so nobody receives a shape their
role shouldn't see."""

import asyncio
import json
import logging

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.domain.privacy import project
from app.realtime.relay import REDIS_URL
from app.security.jwt import TokenError, decode_token

logger = logging.getLogger("ws")
router = APIRouter()


def channel_allowed(role: str, channel: str) -> bool:
    """technical.md §8 channel-authorization table. Ownership checks
    (this emergency belongs to this caller/paramedic/hospital) are deferred
    to the domain layer once B's tables carry enough to check them here --
    documented gap, not silently skipped."""
    if channel == "ops":
        return role in ("developer",)
    if channel.startswith("emergency:"):
        return role in ("patient", "paramedic", "hospital_staff", "developer")
    if channel.startswith("track:"):
        return True  # track tokens are their own auth; access_jwt holders excluded until track_token support lands
    if channel.startswith("ambulance:"):
        return role == "paramedic"
    if channel.startswith("hospital:"):
        return role == "hospital_staff"
    return False


class Subscription:
    def __init__(self, pubsub: redis.client.PubSub, channel: str):
        self.pubsub = pubsub
        self.channel = channel


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str) -> None:
    try:
        claims = decode_token(token, expect_type="access")
    except TokenError:
        await websocket.close(code=4401)
        return

    role = claims["role"]
    await websocket.accept()

    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    subscriptions: dict[str, Subscription] = {}
    listener_tasks: dict[str, asyncio.Task] = {}

    async def listen(sub: Subscription) -> None:
        async for message in sub.pubsub.listen():
            if message["type"] != "message":
                continue
            envelope = json.loads(message["data"])
            envelope["data"] = project(role, envelope["data"])
            await websocket.send_json(envelope)

    try:
        while True:
            msg = await websocket.receive_json()
            op = msg.get("op")

            if op == "ping":
                await websocket.send_json({"event": "pong"})

            elif op == "subscribe":
                channel = msg["channel"]
                if not channel_allowed(role, channel):
                    await websocket.send_json({"event": "error", "data": {"code": "FORBIDDEN", "channel": channel}})
                    continue
                if channel in subscriptions:
                    continue
                pubsub = redis_client.pubsub()
                await pubsub.subscribe(f"ws:{channel}")
                sub = Subscription(pubsub, channel)
                subscriptions[channel] = sub
                listener_tasks[channel] = asyncio.create_task(listen(sub))

            elif op == "unsubscribe":
                channel = msg["channel"]
                sub = subscriptions.pop(channel, None)
                task = listener_tasks.pop(channel, None)
                if task:
                    task.cancel()
                if sub:
                    await sub.pubsub.unsubscribe(f"ws:{channel}")

    except WebSocketDisconnect:
        pass
    finally:
        for task in listener_tasks.values():
            task.cancel()
        for sub in subscriptions.values():
            await sub.pubsub.close()
        await redis_client.aclose()
