"""Auto-discovers every services/ml/app/capabilities/<name>/router.py and
includes its `router` under /ml/v1. Adding a new capability folder is enough —
nobody edits this file to register one (work-distribution.md §2.1)."""

import importlib
import pkgutil
from pathlib import Path

from fastapi import APIRouter, FastAPI

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
    loaded = []
    for name in discover_capability_names():
        module = importlib.import_module(f"{CAPABILITIES_PKG}.{name}.router")
        router: APIRouter = getattr(module, "router")
        app.include_router(router, prefix="/ml/v1", tags=[name])
        loaded.append(name)
    return loaded
