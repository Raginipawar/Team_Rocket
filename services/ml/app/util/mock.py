"""Deterministic, schema-valid mock outputs derived from a hash of the request
body (technical.md §9: every ML endpoint has a mock mode). Same input -> same
output, so frontend/core snapshot tests stay stable."""

import hashlib
import json
from typing import Any


def seed_from_payload(payload: dict[str, Any]) -> int:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return int(hashlib.sha256(blob).hexdigest()[:8], 16)


def pick(seed: int, options: list, salt: str = "") -> Any:
    h = hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest()
    idx = int(h[:8], 16) % len(options)
    return options[idx]


def unit_float(seed: int, salt: str = "") -> float:
    h = hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest()
    return (int(h[:8], 16) % 10_000) / 10_000
