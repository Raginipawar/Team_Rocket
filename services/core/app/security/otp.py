"""OTP generation/verification primitives (technical.md §7.2, §18: 6 digits, 5 min
TTL, 5 attempts, hashed at rest). Pure functions -- storage in `otp_codes`
(db/repos/identity.py, technical.md §5.1) is wired in once B's DB models land."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from .config import get_security_settings


def generate_code() -> str:
    settings = get_security_settings()
    return "".join(secrets.choice("0123456789") for _ in range(settings.otp_length))


def hash_code(code: str, phone: str) -> str:
    # phone salts the hash so the same code for two phones doesn't collide.
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


def verify_code(code: str, phone: str, code_hash: str) -> bool:
    return hash_code(code, phone) == code_hash


def expiry_at() -> datetime:
    settings = get_security_settings()
    return datetime.now(timezone.utc) + timedelta(minutes=settings.otp_ttl_min)


def is_expired(expires_at: datetime) -> bool:
    return datetime.now(timezone.utc) > expires_at
