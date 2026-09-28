from arq import create_pool
from arq.connections import RedisSettings
import os
from urllib.parse import urlparse
from app.jobs.handlers.hospital_control import (
    job_hospital_request_timeout,
    job_hold_expiry,
    job_escalation_repeat,
    job_escalation_default,
    job_extend_hold_on_heartbeat
)

async def startup(ctx):
    pass

async def shutdown(ctx):
    pass

def _redis_settings_from_env() -> RedisSettings:
    url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or 0),
    )

class WorkerSettings:
    functions = [
        job_hospital_request_timeout,
        job_hold_expiry,
        job_escalation_repeat,
        job_escalation_default,
        job_extend_hold_on_heartbeat
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings_from_env()
    max_jobs = 100
    job_timeout = 300

