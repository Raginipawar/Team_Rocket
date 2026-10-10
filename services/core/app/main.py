"""DRAFT -- real owner is Person B (work-distribution.md §2.2: app/main.py,
config.py, deps.py, errors.py, skeleton with routers auto-included). B hasn't
started, so this is the minimum needed to boot-test A's own routers
end-to-end against the real DB. Replace freely; the individual routers in
app/api/v1/** are what matters, not this file."""

import asyncio
import logging
from contextlib import asynccontextmanager

# No basicConfig anywhere meant every app logger (sms, dispatch, main, ...)
# sat below the logging module's WARNING-level lastResort handler and was
# silently swallowed -- including SMS_MODE=fake's own "here's the OTP code"
# log line, discovered when a real OTP request produced no visible code.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

from fastapi import FastAPI

from app.api.v1 import (
    ambulance, analytics, auth, clinical, emergencies, hospital, me, offers, ops,
    webhooks_sms, webhooks_telegram,
)
from app.db.session import get_session
from app.domain.lifecycle_monitor import run_lifecycle_monitor_forever
from app.jobs.ml_feeder import run_feeder_forever
from app.realtime.relay import run_relay_forever
from app.realtime.ws import router as ws_router
from app.security.middleware import CorrelationIdMiddleware, IdempotencyMiddleware

logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # run_relay_forever (realtime/relay.py) is what actually moves committed
    # outbox rows onto Redis pub/sub -> the WS clients. It existed as a
    # callable "simple asyncio loop" but nothing anywhere ever called it --
    # every outbox row would sit with sent_at IS NULL forever, and no WS
    # client (patient/paramedic/hospital_staff/family) would ever receive a
    # single live event, found by checking what actually starts it (nothing).
    relay_task = asyncio.create_task(run_relay_forever(get_session))
    monitor_task = asyncio.create_task(run_lifecycle_monitor_forever(get_session))
    # ml_feeder (jobs/ml_feeder.py): demand-forecast and pre-positioning had
    # NO caller anywhere -- both only worked if someone manually built the
    # feature payload and called the ML service directly. This starts the
    # real 15-minute job (technical.md A16/Section11.15).
    feeder_task = asyncio.create_task(run_feeder_forever(get_session))
    background_tasks = (relay_task, monitor_task, feeder_task)
    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="GoldenHour Core (draft)", version="0.1.0", lifespan=lifespan)

app.add_middleware(IdempotencyMiddleware)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(emergencies.router, prefix="/api/v1", tags=["emergencies"])
app.include_router(offers.router, prefix="/api/v1/ambulance", tags=["dispatch"])
app.include_router(ambulance.router, prefix="/api/v1/ambulance", tags=["ambulance"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(me.router, prefix="/api/v1", tags=["me"])
app.include_router(webhooks_sms.router, prefix="/api/v1", tags=["webhooks"])
# Person B's routers: existed as real files but were never mounted anywhere --
# the running app only ever served Person A's own routes. Each already
# defines its own sub-path (hospital.py -> /hospital, clinical.py ->
# /emergencies, ops.py -> /ops, webhooks_telegram.py -> /webhooks/telegram),
# so only the shared /api/v1 prefix is added here, same as emergencies.router above.
app.include_router(hospital.router, prefix="/api/v1", tags=["hospital"])
app.include_router(clinical.router, prefix="/api/v1", tags=["clinical"])
app.include_router(ops.router, prefix="/api/v1", tags=["ops"])
app.include_router(webhooks_telegram.router, prefix="/api/v1", tags=["webhooks"])
app.include_router(ws_router, tags=["realtime"])


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok"}


# Frontend's HealthProvider (apps/web/app/providers.tsx) polls bare /readyz
# every 5s via the /core/readyz rewrite and shows a full-width "We cannot
# reach GoldenHour, call 108" banner after 2 consecutive failures. Neither
# /readyz nor /healthz existed anywhere on this app, so that banner was
# showing permanently regardless of whether the rest of the backend worked --
# confirmed via the 404s on every single poll in the server log.
@app.get("/readyz")
@app.get("/healthz")
async def readyz() -> dict:
    return {"status": "ok"}
