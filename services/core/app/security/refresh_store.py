"""Refresh-token revocation (technical.md §18: 'refresh tokens rotated and
revocable'). Each refresh token's jti is tracked; on /auth/refresh the old
jti is revoked and a new refresh token issued (rotation), so a stolen,
already-used refresh token can't be replayed. Redis-backed with an
in-memory fallback, same pattern as security/rate_limit.py."""

from .config import get_security_settings
from .rate_limit import _get_client

_memory_revoked: set[str] = set()


async def revoke(jti: str, ttl_sec: int | None = None) -> None:
    client = _get_client()
    ttl = ttl_sec or get_security_settings().refresh_token_ttl_days * 86400
    if client is not None:
        try:
            await client.set(f"revoked_jti:{jti}", "1", ex=ttl)
            return
        except Exception:
            pass
    _memory_revoked.add(jti)


async def is_revoked(jti: str) -> bool:
    client = _get_client()
    if client is not None:
        try:
            return bool(await client.exists(f"revoked_jti:{jti}"))
        except Exception:
            pass
    return jti in _memory_revoked
