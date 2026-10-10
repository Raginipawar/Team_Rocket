import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import importlib
import httpx
from sqlalchemy import text
import redis.asyncio as redis

from app.errors import install_error_handlers
from app.db.engine import engine
from app.config import settings
from app.realtime.ws import router as ws_router
from app.security.middleware import CorrelationIdMiddleware, IdempotencyMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(title="GoldenHour Core API", version="0.1.0")

app.add_middleware(IdempotencyMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)

app.include_router(ws_router, tags=["realtime"])

# Include API v1 routers
routers = [
    ("app.api.v1.auth", "router"),
    ("app.api.v1.emergencies", "router"),
    ("app.api.v1.ambulance", "router"),
    ("app.api.v1.offers", "router"),
    ("app.api.v1.analytics", "router"),
    ("app.api.v1.me", "router"),
    ("app.api.v1.webhooks_sms", "router"),
    ("app.api.v1.hospital", "router"),
    ("app.api.v1.clinical", "router"),
    ("app.api.v1.ops", "router"),
    ("app.api.v1.health", "router"),
    ("app.api.v1.webhooks_telegram", "router"),
]

for module_name, router_name in routers:
    try:
        module = importlib.import_module(module_name)
        router = getattr(module, router_name)
        app.include_router(router, prefix="/api/v1")
        logger.info(f"Mounted router from {module_name}")
    except (ImportError, AttributeError) as e:
        logger.warning(f"Skipping {module_name}: {e}")

@app.on_event("startup")
async def startup_event():
    logger.info("GoldenHour Core ready")

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/readyz")
async def readyz():
    status = {"db": "ok", "redis": "ok", "ml": "ok", "osrm": "ok"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        status["db"] = "error"
        
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
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
            res = await client.get(f"{settings.OSRM_URL}")
            # OSRM will return 400 on root, but connection succeeds
            if res.status_code not in [200, 400]:
                status["osrm"] = "error"
    except Exception:
        status["osrm"] = "error"
        
    return {"status": status}
