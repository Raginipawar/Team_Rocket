"""Auto-discovers every services/ml/app/capabilities/<name>/router.py and
includes its `router` under /ml/v1. Adding a new capability folder is enough —
nobody edits this file to register one (work-distribution.md §2.1)."""

import importlib
import logging
import pkgutil
from pathlib import Path

from fastapi import APIRouter, FastAPI

logger = logging.getLogger("registry")

CAPABILITIES_PKG = "app.capabilities"
CAPABILITIES_DIR = Path(__file__).parent / "capabilities"


def discover_capability_names() -> list[str]:
    if not CAPABILITIES_DIR.exists():
        return []
    return sorted(
        p.name for p in CAPABILITIES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "router.py").exists()
    )


def include_all_routers(app: FastAPI) -> list[str]:
    """One capability's broken import (e.g. a numpy/pandas/bottleneck version
    conflict pulled in by lightgbm) used to crash the ENTIRE ML service at
    startup -- all 20 capabilities down because of one, found by actually
    trying to boot it. Each import is now isolated: a failure is logged and
    that capability is skipped, the other 19 still come up."""
    loaded = []
    for name in discover_capability_names():
        try:
            module = importlib.import_module(f"{CAPABILITIES_PKG}.{name}.router")
            router: APIRouter = getattr(module, "router")
            app.include_router(router, prefix="/ml/v1", tags=[name])
            loaded.append(name)
        except Exception:
            logger.exception("capability '%s' failed to load -- skipped, other capabilities still start", name)
    return loaded
