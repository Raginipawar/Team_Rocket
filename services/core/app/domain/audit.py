from uuid import UUID
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

async def write(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    actor_id: Optional[UUID],
    action: str,
    changes: Dict[str, Any],
    metadata: Dict[str, Any] = None
) -> None:
    """
    Inserts a record into the audit_log table.
    """
    import json
    stmt = text(\"\"\"
        INSERT INTO audit_logs (entity_type, entity_id, actor_id, action, changes, metadata, created_at)
        VALUES (:entity_type, :entity_id, :actor_id, :action, :changes, :metadata, now())
    \"\"\")
    await db.execute(stmt, {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "actor_id": str(actor_id) if actor_id else None,
        "action": action,
        "changes": json.dumps(changes),
        "metadata": json.dumps(metadata) if metadata else "{}"
    })
