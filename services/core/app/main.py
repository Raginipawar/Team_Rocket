"""DRAFT -- real owner is Person B (work-distribution.md §2.2: app/main.py,
config.py, deps.py, errors.py, skeleton with routers auto-included). B hasn't
started, so this is the minimum needed to boot-test A's own routers
end-to-end against the real DB. Replace freely; the individual routers in
app/api/v1/** are what matters, not this file."""

from fastapi import FastAPI

from app.api.v1 import emergencies

app = FastAPI(title="GoldenHour Core (draft)", version="0.1.0")
app.include_router(emergencies.router, prefix="/api/v1", tags=["emergencies"])


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok"}
