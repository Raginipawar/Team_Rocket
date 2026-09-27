"""Generic one-time token primitive (technical.md §18: 32 random bytes, stored
SHA-256 hashed, single use, short TTL). Used for family tracking links and ops
one-time links; storage/TTL enforcement lives in the owning domain module."""

import hashlib
import secrets


def new_token() -> tuple[str, str]:
    """Returns (raw_token_to_hand_to_client, sha256_hash_to_store)."""
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
