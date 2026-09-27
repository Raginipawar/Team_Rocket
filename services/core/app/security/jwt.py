"""HS256 JWT with rotation-ready key id (technical.md §7.1, §18).
Claims: sub, role, hospital_id?, ambulance_id?, type ("access"|"refresh"), exp, iat, kid."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt

from .config import get_security_settings


class TokenError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(claims: dict, ttl: timedelta) -> str:
    settings = get_security_settings()
    now = _now()
    payload = {
        **claims,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        headers={"kid": settings.jwt_kid},
    )


def create_access_token(*, sub: str, role: str, hospital_id: str | None = None,
                         ambulance_id: str | None = None) -> str:
    settings = get_security_settings()
    claims = {"sub": sub, "role": role, "type": "access"}
    if hospital_id:
        claims["hospital_id"] = hospital_id
    if ambulance_id:
        claims["ambulance_id"] = ambulance_id
    return _encode(claims, timedelta(minutes=settings.access_token_ttl_min))


def create_refresh_token(*, sub: str, role: str) -> str:
    settings = get_security_settings()
    claims = {"sub": sub, "role": role, "type": "refresh"}
    return _encode(claims, timedelta(days=settings.refresh_token_ttl_days))


def decode_token(token: str, *, expect_type: Literal["access", "refresh"] = "access") -> dict:
    settings = get_security_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid token") from exc

    if claims.get("type") != expect_type:
        raise TokenError(f"expected {expect_type} token")
    return claims
