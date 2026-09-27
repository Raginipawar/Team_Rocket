from arq import create_pool
from arq.connections import RedisSettings
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
    redis_settings = RedisSettings()
    max_jobs = 100
    job_timeout = 300
