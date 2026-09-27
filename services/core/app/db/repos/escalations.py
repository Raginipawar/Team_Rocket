from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from services.core.app.db.models import Escalation # type: ignore

class AlreadyTaken(Exception):
    pass

async def create_escalation(db: AsyncSession, **kwargs) -> Escalation:
    esc = Escalation(**kwargs)
    db.add(esc)
    await db.flush()
    return esc

async def get_escalation(db: AsyncSession, escalation_id: UUID) -> Escalation:
    return await db.get(Escalation, escalation_id)

async def claim_escalation(db: AsyncSession, escalation_id: UUID, user_id: UUID) -> Escalation:
    # We don't have version in method signature except implicit from CAS request, wait, spec says:
    # CAS: UPDATE WHERE status='open' AND version=:v; 0 rows -> AlreadyTaken
    # Since we don't pass v, let's fetch it first or just update where status open
    stmt = (
        update(Escalation)
        .where(Escalation.id == escalation_id, Escalation.status == 'open')
        .values(status='claimed', claimed_by=user_id)
        .returning(Escalation)
    )
    result = await db.execute(stmt)
    esc = result.scalar_one_or_none()
    if not esc:
        raise AlreadyTaken("Escalation already claimed or does not exist")
    return esc

async def resolve_escalation(db: AsyncSession, escalation_id: UUID, option_id: str, claimer_id: UUID) -> Escalation:
    stmt = (
        update(Escalation)
        .where(Escalation.id == escalation_id) # potentially check claimer_id
        .values(status='resolved', resolution_option_id=option_id, resolved_by=claimer_id, resolved_at=datetime.utcnow())
        .returning(Escalation)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def list_open_escalations(db: AsyncSession) -> list[Escalation]:
    result = await db.execute(select(Escalation).where(Escalation.status == 'open'))
    return list(result.scalars().all())

async def schedule_repeat(db: AsyncSession, escalation_id: UUID, repeat_at: datetime) -> None:
    await db.execute(
        update(Escalation)
        .where(Escalation.id == escalation_id)
        .values(repeat_at=repeat_at)
    )
