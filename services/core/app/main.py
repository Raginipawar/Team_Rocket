import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.errors import install_error_handlers
from app.db.engine import engine
from sqlalchemy import text
import redis.asyncio as redis
from app.config import settings
import httpx

logger = logging.getLogger(__name__)

app = FastAPI(title="GoldenHour Core API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)

# Include API v1 routers
from app.api.v1.hospital import router as hospital_router
from app.api.v1.clinical import router as clinical_router
from app.api.v1.ops import router as ops_router
from app.api.v1.health import router as health_router
from app.api.v1.webhooks_telegram import router as telegram_router

app.include_router(hospital_router, prefix="/api/v1")
app.include_router(clinical_router, prefix="/api/v1")
app.include_router(ops_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(telegram_router, prefix="/api/v1")

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
            res = await client.get(f"{settings.ML_BASE_URL}/health")
            if res.status_code != 200:
                status["ml"] = "error"
    except Exception:
        status["ml"] = "error"
        
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            res = await client.get(f"{settings.OSRM_URL}/health")
            if res.status_code != 200:
                status["osrm"] = "error"
    except Exception:
        status["osrm"] = "error"
        
    return {"status": status}
