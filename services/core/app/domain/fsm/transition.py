from typing import Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from ..audit import write as audit_write
import json

class InvalidTransition(Exception):
    pass

class VersionConflict(Exception):
    pass

class NotFound(Exception):
    pass

async def apply_transition(
    db: AsyncSession,
    *,
    model_class,
    entity_id: UUID,
    expected_status: str,
    new_status: str,
    expected_version: int,
    fsm,
    extra_updates: dict = {},
    audit_kwargs: dict,
    outbox_event: dict,
) -> Any:
    """Single CAS UPDATE + audit + outbox in one transaction."""
    fsm.validate_transition(expected_status, new_status)
    
    update_data = {"status": new_status, "version": expected_version + 1, **extra_updates}
    
    stmt = (
        update(model_class)
        .where(model_class.id == entity_id, model_class.version == expected_version, model_class.status == expected_status)
        .values(**update_data)
        .returning(model_class)
    )
    result = await db.execute(stmt)
    updated_entity = result.scalar_one_or_none()
    
    if not updated_entity:
        # Check if it exists
        check = await db.get(model_class, entity_id)
        if not check:
            raise NotFound(f"Entity {entity_id} not found")
        raise VersionConflict(f"Version or status mismatch for {entity_id}")
    
    await audit_write(db, **audit_kwargs)
    
    # Write to outbox (assuming outbox model is imported/available, or using raw SQL, or event_bus model)
    from app.db.models import OutboxEvent # placeholder, depending on actual models
    outbox_record = OutboxEvent(
        aggregate_type=outbox_event.get("aggregate_type", model_class.__name__),
        aggregate_id=str(entity_id),
        event_type=outbox_event.get("event_type", f"{model_class.__name__}StateChanged"),
        payload=outbox_event.get("payload", {})
    )
    db.add(outbox_record)
    
    return updated_entity
