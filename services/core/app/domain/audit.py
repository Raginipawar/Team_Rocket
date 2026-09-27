"""DRAFT stub -- real owner is Person B (work-distribution.md §2.2, frozen at
hour 3). B has not started; A's intake pipeline needs *some* audit.write to
call today (technical.md's "one transaction = state + audit + outbox" rule),
so this writes to the real audit_log table using the exact signature
work-distribution.md §4.2 promises. Replace with B's version -- keep the
signature so callers don't change."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def write(
    session: AsyncSession, *,
    actor_type: str, actor_id: str, entity: str, entity_id: UUID | str,
    action: str, before: dict | None, after: dict | None,
    reason: str | None = None, model_version: str | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO audit_log (actor_type, actor_id, entity, entity_id, action, before, after, reason, model_version) "
            "VALUES (:actor_type, :actor_id, :entity, :entity_id, :action, "
            "CAST(:before AS jsonb), CAST(:after AS jsonb), :reason, :model_version)"
        ),
        {
            "actor_type": actor_type, "actor_id": actor_id, "entity": entity,
            "entity_id": str(entity_id), "action": action,
            "before": _to_json(before), "after": _to_json(after),
            "reason": reason, "model_version": model_version,
        },
    )


def _to_json(obj: dict | None) -> str:
    import json
    return json.dumps(obj if obj is not None else {})
