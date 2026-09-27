"""Shared per-capability dispatch: every capability's router.py calls
`resolve(name, real_fn, mock_fn, payload)` so the ML_MODE / ML_MOCK_CAPABILITIES
switch (technical.md §9, §17) lives in one place instead of being reimplemented
11 times."""

import time
from typing import Awaitable, Callable, TypeVar

from app.config import get_settings

T = TypeVar("T")


async def resolve(
    capability: str,
    real_fn: Callable[..., Awaitable[dict]],
    mock_fn: Callable[..., dict],
    payload: dict,
) -> dict:
    settings = get_settings()
    mode = settings.capability_mode(capability)
    start = time.perf_counter()

    if mode == "mock":
        result = mock_fn(payload)
    else:
        result = await real_fn(payload)

    result.setdefault("model_version", f"{capability}:{mode}:v0")
    result.setdefault("latency_ms", round((time.perf_counter() - start) * 1000, 1))
    return result
