from uuid import UUID

async def job_hospital_request_timeout(ctx, request_id: UUID, acuity: str) -> None:
    pass

async def job_hold_expiry(ctx, reservation_id: UUID) -> None:
    pass

async def job_escalation_repeat(ctx, escalation_id: UUID) -> None:
    pass

async def job_escalation_default(ctx, escalation_id: UUID) -> None:
    pass

async def job_extend_hold_on_heartbeat(ctx, emergency_id: UUID, eta_remaining_sec: int) -> None:
    pass
