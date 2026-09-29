from uuid import UUID
from datetime import datetime
from typing import Optional
from arq import ArqRedis

async def schedule(pool: ArqRedis, job_name: str, args: tuple, *, defer_by_s: Optional[float] = None, job_id: Optional[str] = None) -> None:
    await pool.enqueue_job(job_name, *args, _defer_by=defer_by_s, _job_id=job_id)

async def schedule_hospital_timeout(pool: ArqRedis, request_id: UUID, acuity: str, expires_at: datetime) -> None:
    delay = max((expires_at - datetime.utcnow()).total_seconds(), 0)
    await schedule(pool, "job_hospital_request_timeout", (request_id, acuity), defer_by_s=delay)

async def schedule_offer_expiry(pool: ArqRedis, offer_id: UUID, expires_at: datetime) -> None:
    pass

async def schedule_hold_expiry(pool: ArqRedis, reservation_id: UUID, expires_at: datetime) -> None:
    delay = max((expires_at - datetime.utcnow()).total_seconds(), 0)
    await schedule(pool, "job_hold_expiry", (reservation_id,), defer_by_s=delay)

async def schedule_escalation_repeat(pool: ArqRedis, escalation_id: UUID, repeat_at: datetime) -> None:
    delay = max((repeat_at - datetime.utcnow()).total_seconds(), 0)
    await schedule(pool, "job_escalation_repeat", (escalation_id,), defer_by_s=delay)

async def schedule_escalation_default(pool: ArqRedis, escalation_id: UUID, default_at: datetime) -> None:
    delay = max((default_at - datetime.utcnow()).total_seconds(), 0)
    await schedule(pool, "job_escalation_default", (escalation_id,), defer_by_s=delay)
