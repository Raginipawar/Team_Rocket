"""Redis-backed fixed-window rate limiter (technical.md §18: OTP, SOS/phone,
SMS inbound, login). Falls back to an in-process dict when Redis is
unreachable, so routes still work before `docker compose up` -- never crashes
the request path, just stops limiting until Redis is back."""

import time

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover
    redis = None

from .config import get_security_settings

_memory_store: dict[str, tuple[int, float]] = {}
_client = None


def _get_client():
    global _client
    if redis is None:
        return None
    if _client is None:
        _client = redis.from_url(get_security_settings().redis_url, decode_responses=True)
    return _client


async def hit(key: str, *, limit: int, window_sec: int) -> bool:
    """Returns True if this call is within the limit (and records it)."""
    client = _get_client()
    if client is not None:
        try:
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, window_sec)
            return count <= limit
        except Exception:  # redis down -> fall through to memory
            pass

    now = time.time()
    count, reset_at = _memory_store.get(key, (0, now + window_sec))
    if now > reset_at:
        count, reset_at = 0, now + window_sec
    count += 1
    _memory_store[key] = (count, reset_at)
    return count <= limit
