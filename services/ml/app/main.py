import time

from fastapi import FastAPI

from app.registry import discover_capability_names, include_all_routers

app = FastAPI(title="GoldenHour ML Service", version="0.1.0")

_START = time.time()
_LOADED_CAPABILITIES: list[str] = []


@app.on_event("startup")
async def _startup() -> None:
    global _LOADED_CAPABILITIES
    _LOADED_CAPABILITIES = include_all_routers(app)


@app.get("/ml/v1/health")
async def health() -> dict:
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"
    return {
        "status": "ok",
        "uptime_s": round(time.time() - _START, 1),
        "device": device,
        "capabilities": _LOADED_CAPABILITIES or discover_capability_names(),
    }
