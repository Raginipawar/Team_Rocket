"""DRAFT stub -- real owner is Person B (work-distribution.md §2.2, §13 escalation
engine). B has not started; A's intake pipeline needs to trigger a mass-casualty
escalation (technical.md §10.1 step 7) today, so this writes a minimal
`escalations` row using the exact signature work-distribution.md §4.2 promises.
No Telegram/timers yet -- that's B's real engine (technical.md §13)."""

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def raise_escalation(
    session: AsyncSession, *, type: str, emergency_id: UUID | str | None = None,
    incident_id: UUID | str | None = None, context: dict,
) -> str:
    row = (await session.execute(
        text(
            "INSERT INTO escalations (type, emergency_id, incident_id, summary, options, default_option_id) "
            "VALUES (:type, :emergency_id, :incident_id, :summary, CAST(:options AS jsonb), :default_option_id) "
            "RETURNING id"
        ),
        {
            "type": type,
            "emergency_id": str(emergency_id) if emergency_id else None,
            "incident_id": str(incident_id) if incident_id else None,
            "summary": context.get("summary", f"{type} escalation (stub engine, no Telegram yet)"),
            "options": json.dumps(context.get("options", [])),
            "default_option_id": context.get("default_option_id"),
        },
    )).scalar_one()
    return str(row)
