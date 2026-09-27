import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.core.app.errors import install_error_handlers
from services.core.app.db.engine import engine
from sqlalchemy import text
import redis.asyncio as redis
from services.core.app.config import settings
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

# Attempt to include routers
try:
    from services.core.app.routers import api_router
    app.include_router(api_router, prefix="/api/v1")
except ImportError as e:
    logger.warning(f"Failed to import routers: {e}")

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
