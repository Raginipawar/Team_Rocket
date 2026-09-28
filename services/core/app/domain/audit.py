from uuid import UUID
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json

async def write(
    db: AsyncSession,
    table_name: str,
    record_id: str,
    action: str,
    actor_id: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
    **kwargs: Any
) -> None:
    """
    Inserts a record into the audit_log table.
    """
    stmt = text("""
        INSERT INTO audit_log (table_name, record_id, action, actor_id, changes)
        VALUES (:table_name, :record_id, :action, :actor_id, :changes)
    """)
    await db.execute(stmt, {
        "table_name": table_name,
        "record_id": str(record_id),
        "action": action,
        "actor_id": str(actor_id) if actor_id else None,
        "changes": json.dumps(changes or {})
    })
