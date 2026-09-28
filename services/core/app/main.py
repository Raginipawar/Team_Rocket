"""DRAFT -- real owner is Person B (work-distribution.md §2.2: app/main.py,
config.py, deps.py, errors.py, skeleton with routers auto-included). B hasn't
started, so this is the minimum needed to boot-test A's own routers
end-to-end against the real DB. Replace freely; the individual routers in
app/api/v1/** are what matters, not this file."""

from fastapi import FastAPI

from app.api.v1 import ambulance, analytics, auth, emergencies, me, offers, webhooks_sms
from app.realtime.ws import router as ws_router
from app.security.middleware import CorrelationIdMiddleware, IdempotencyMiddleware

app = FastAPI(title="GoldenHour Core (draft)", version="0.1.0")

app.add_middleware(IdempotencyMiddleware)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(emergencies.router, prefix="/api/v1", tags=["emergencies"])
app.include_router(offers.router, prefix="/api/v1/ambulance", tags=["dispatch"])
app.include_router(ambulance.router, prefix="/api/v1/ambulance", tags=["ambulance"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(me.router, prefix="/api/v1", tags=["me"])
app.include_router(webhooks_sms.router, prefix="/api/v1", tags=["webhooks"])
app.include_router(ws_router, tags=["realtime"])


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok"}
