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

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import (
    ambulance, analytics, auth, clinical, emergencies, hospital, me, offers, ops,
    registration, webhooks_sms, webhooks_telegram,
)
from app.config import settings
from app.db.engine import engine
from app.db.session import get_session
from app.domain.lifecycle_monitor import run_lifecycle_monitor_forever
from app.errors import install_error_handlers
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
app.add_middleware(
    # allow_origins=["*"] with allow_credentials=True is invalid per the CORS
    # spec (browsers require an explicit origin, not a wildcard, when
    # credentials are included) -- not currently exercised since the
    # frontend talks to this same-origin via Next.js rewrites, but wrong
    # either way, so not copied from the source this was adapted from.
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(registration.router, prefix="/api/v1", tags=["registration"])
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


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


# Frontend's HealthProvider (apps/web/app/providers.tsx) polls bare /readyz
# every 5s via the /core/readyz rewrite and shows a full-width "We cannot
# reach GoldenHour, call 108" banner after 2 consecutive failures based on
# HTTP status alone (fetch .ok), not the body -- neither /readyz nor
# /healthz existed anywhere on this app at first (confirmed via the 404s on
# every single poll in the server log), so that banner was showing
# permanently. Now reports which real dependency is actually down (DB,
# Redis, ML service, OSRM) in the body while always returning 200, so the
# frontend banner only fires on this server being genuinely unreachable,
# not on one dependency having a bad moment.
@app.get("/readyz")
async def readyz() -> dict:
    status = {"db": "ok", "redis": "ok", "ml": "ok", "osrm": "ok"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        status["db"] = "error"

    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
    except Exception:
        status["redis"] = "error"

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            res = await client.get(f"{settings.ML_BASE_URL}/ml/v1/health")
            if res.status_code != 200:
                status["ml"] = "error"
    except Exception:
        status["ml"] = "error"

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            res = await client.get(settings.OSRM_URL)
            # OSRM returns 400 on a bare root request -- a reachable server,
            # just not a route query -- so 400 counts as "ok" here too.
            if res.status_code not in (200, 400):
                status["osrm"] = "error"
    except Exception:
        status["osrm"] = "error"

    return {"status": "ok", "dependencies": status}


# Temporary: Render's free plan has no Shell tab, and this venue's network
# blocks direct outbound connections to Render's external Postgres (same
# TLS-handshake-timeout pattern seen with Tailscale/ngrok here), so there's
# no other way to run the one-off migration against the deployed DB. Guarded
# by MIGRATE_KEY (unset by default -- route 403s until someone deliberately
# sets it as a Render env var). Remove once proper CI/CD migrations exist.
@app.post("/internal/migrate")
async def run_migrations(x_migrate_key: str = Header(default="")):
    if not settings.MIGRATE_KEY or x_migrate_key != settings.MIGRATE_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    from scripts.apply_sql_migrations import apply_all
    applied = await apply_all(settings.DATABASE_URL)
    return {"applied": applied}


# Temporary: same no-Shell-tab problem as /internal/migrate above -- needed
# a one-off way to wipe accumulated test ambulances/emergencies/offers
# without touching real accounts (users/hospitals/families stay put).
# Remove once this round of manual testing is done.
# A turnkey demo target for the hospital Data Integration card -- paste
# this exact URL as the endpoint (any string works as the API key, it's
# not checked) and Sync now pulls real-looking numbers immediately, no
# external service, Supabase project or anything else to stand up first.
# Slightly randomised each call so repeated syncs visibly change something.
@app.get("/internal/demo-hospital-feed")
async def demo_hospital_feed():
    import random
    types = ["ventilator", "cath_lab", "ct_scanner", "mri", "defibrillator",
             "blood_o_neg", "blood_o_pos", "blood_a_pos", "blood_b_pos", "blood_ab_pos",
             "dialysis", "operating_theatre"]
    return {"resources": [
        {"type": t, "available": random.randint(0, 20), "total": 20} for t in types
    ]}


# Lets me see exactly what's stored and attempt the sync server-side
# myself, instead of relaying toast text back and forth over chat.
@app.get("/internal/debug-hospitals")
async def debug_hospitals(x_migrate_key: str = Header(default="")):
    if not settings.MIGRATE_KEY or x_migrate_key != settings.MIGRATE_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    async with get_session() as session:
        rows = (await session.execute(text("""
            SELECT id, name, integration_mode, integration_endpoint_url,
                   (integration_api_key IS NOT NULL) AS api_key_set,
                   integration_last_synced_at
            FROM hospitals ORDER BY updated_at DESC
        """))).mappings().all()
    return [dict(r) for r in rows]


# Fixes the stored endpoint URL directly -- the settings page UI keeps
# saving just the bare project URL (missing /rest/v1/<table>?select=...),
# this appends it server-side so it's correct without another round trip.
@app.post("/internal/debug-fix-endpoint")
async def debug_fix_endpoint(hospital_id: str, table: str = "hospital_capacity", x_migrate_key: str = Header(default="")):
    if not settings.MIGRATE_KEY or x_migrate_key != settings.MIGRATE_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    async with get_session() as session:
        base = (await session.execute(
            text("SELECT integration_endpoint_url FROM hospitals WHERE id = :id"), {"id": hospital_id},
        )).scalar_one_or_none()
        if not base:
            raise HTTPException(404, "hospital has no endpoint_url set")
        fixed = base.split("/rest/v1/")[0].rstrip("/") + f"/rest/v1/{table}?select=type,available,total"
        await session.execute(
            text("UPDATE hospitals SET integration_endpoint_url = :url WHERE id = :id"),
            {"url": fixed, "id": hospital_id},
        )
        await session.commit()
    return {"fixed_url": fixed}


@app.post("/internal/debug-sync-hospital")
async def debug_sync_hospital(hospital_id: str, x_migrate_key: str = Header(default="")):
    if not settings.MIGRATE_KEY or x_migrate_key != settings.MIGRATE_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    from app.domain.integration_sync import sync_hospital_from_api, SyncError
    async with get_session() as session:
        try:
            result = await sync_hospital_from_api(session, hospital_id)
            await session.commit()
            return {"status": "ok", **result}
        except SyncError as e:
            return {"status": "error", "message": str(e)}


# Removes the seeded demo hospital (0009_demo_seed.sql's "Greenfield Heart
# Centre", is_simulated=true) and everything tied to it, leaving real
# registered hospitals untouched -- its id is hardcoded in that migration.
@app.post("/internal/remove-demo-hospital")
async def remove_demo_hospital(x_migrate_key: str = Header(default="")):
    if not settings.MIGRATE_KEY or x_migrate_key != settings.MIGRATE_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    hid = "a61d76bf-457c-47c0-bee7-134134835119"
    async with get_session() as session:
        name = (await session.execute(text("SELECT name FROM hospitals WHERE id = :id"), {"id": hid})).scalar_one_or_none()
        if name is None:
            return {"status": "already removed"}
        await session.execute(text("UPDATE users SET hospital_id = NULL WHERE hospital_id = :id"), {"id": hid})
        await session.execute(text("UPDATE emergencies SET hospital_id = NULL WHERE hospital_id = :id"), {"id": hid})
        for stmt in [
            "DELETE FROM staff_shifts WHERE staff_id IN (SELECT id FROM staff WHERE hospital_id = :id)",
            "DELETE FROM staff WHERE hospital_id = :id",
            "DELETE FROM hospital_occupancy_history WHERE hospital_id = :id",
            "DELETE FROM hospital_resources WHERE hospital_id = :id",
            "DELETE FROM rooms WHERE hospital_id = :id",
            "DELETE FROM reservations WHERE hospital_id = :id",
            "DELETE FROM hospital_requests WHERE hospital_id = :id",
            "DELETE FROM handoffs WHERE hospital_id = :id",
            "DELETE FROM hospitals WHERE id = :id",
        ]:
            await session.execute(text(stmt), {"id": hid})
        await session.commit()
    return {"status": "removed", "name": name}


@app.post("/internal/reset-test-data")
async def reset_test_data(x_migrate_key: str = Header(default="")):
    if not settings.MIGRATE_KEY or x_migrate_key != settings.MIGRATE_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    async with get_session() as session:
        await session.execute(text("UPDATE users SET ambulance_id = NULL WHERE ambulance_id IS NOT NULL"))
        for stmt in [
            "DELETE FROM patients", "DELETE FROM dispatch_offers", "DELETE FROM hospital_requests",
            "DELETE FROM reservation_items", "DELETE FROM reservations", "DELETE FROM handoffs",
            "DELETE FROM escalations", "DELETE FROM followup_answers", "DELETE FROM triage_confirmations",
            "DELETE FROM sms_messages WHERE emergency_id IS NOT NULL",
            "DELETE FROM ml_predictions WHERE emergency_id IS NOT NULL",
            "DELETE FROM one_time_tokens WHERE emergency_id IS NOT NULL OR escalation_id IS NOT NULL",
            "DELETE FROM ambulance_status_log", "DELETE FROM emergencies", "DELETE FROM incidents",
            "DELETE FROM ambulances",
        ]:
            await session.execute(text(stmt))
        await session.commit()
    return {"status": "wiped"}


# Temporary: no Shell tab on Render's free plan to just run a SELECT by
# hand -- same constraint the two routes above exist for. Dumps exactly
# what dispatch itself sees for the most recent emergency, to stop
# guessing from HTTP status codes alone.
@app.get("/internal/debug-dispatch")
async def debug_dispatch(x_migrate_key: str = Header(default="")):
    if not settings.MIGRATE_KEY or x_migrate_key != settings.MIGRATE_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    from app.db.repos import emergencies as emergencies_repo
    from app.domain import tracking
    async with get_session() as session:
        latest_row = (await session.execute(text(
            "SELECT id FROM emergencies ORDER BY created_at DESC LIMIT 1"
        ))).mappings().first()
        emergency = await emergencies_repo.get_emergency(session, str(latest_row["id"])) if latest_row else None
        ambulance_view = (
            await tracking.get_ambulance_view(session, str(emergency["ambulance_id"]), emergency)
            if emergency and emergency.get("ambulance_id") else None
        )
        ambulances = (await session.execute(text("""
            SELECT id, registration_no, status, kyc_verified, type, last_heartbeat_at,
                   ST_Y(current_location::geometry) AS lat, ST_X(current_location::geometry) AS lng,
                   now() - last_heartbeat_at AS heartbeat_age
            FROM ambulances
        """))).mappings().all()
        offers = (await session.execute(text("""
            SELECT id, emergency_id, ambulance_id, round, status, offered_at, expires_at
            FROM dispatch_offers ORDER BY offered_at DESC LIMIT 10
        """))).mappings().all()
    return {
        "latest_emergency": emergency,
        "ambulance_view": ambulance_view,
        "ambulances": [dict(a) for a in ambulances],
        "recent_offers": [dict(o) for o in offers],
    }
