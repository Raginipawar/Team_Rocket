from uuid import UUID
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.audit import write as domain_write

async def write_audit(
    db: AsyncSession,
    entity_type: str,
    entity_id: UUID,
    actor_id: Optional[UUID],
    action: str,
    changes: Dict[str, Any],
    metadata: Dict[str, Any] = None
) -> None:
    """Thin wrapper calling domain.audit.write"""
    await domain_write(db, entity_type, entity_id, actor_id, action, changes, metadata)
