"""Escalation engine (technical.md §13 crisis escalation). Writes the real
`escalations` row, then sends the real Telegram alert with claim/option
buttons and a one-time ops link -- previously wrote the row and stopped
there, with nothing (not Telegram, not timers) ever notifying the team a
crisis had actually happened. TELEGRAM_MODE=fake still just logs, same
honest fake/real split as SMS."""

import json
import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("escalation")


class _EscalationView:
    """Lightweight stand-in for the ORM row -- send_escalation_alert only
    reads .id/.type/.summary/.options, and the INSERT below is a raw query
    (not the ORM), so there's no row object to hand it without a second
    round-trip."""
    def __init__(self, id: str, type: str, summary: str, options: list):
        self.id = id
        self.type = type
        self.summary = summary
        self.options = options


async def raise_escalation(
    session: AsyncSession, *, type: str, emergency_id: UUID | str | None = None,
    incident_id: UUID | str | None = None, context: dict,
) -> str:
    summary = context.get("summary", f"{type} escalation")
    options = context.get("options", [])
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
            "summary": summary,
            "options": json.dumps(options, default=str),
            "default_option_id": context.get("default_option_id"),
        },
    )).scalar_one()
    escalation_id = str(row)

    try:
        from app.domain.ops import issue_ops_token
        from app.integrations.telegram.client import send_escalation_alert

        ops_link = await issue_ops_token(session, escalation_id=escalation_id, emergency_id=emergency_id)
        message_ids = await send_escalation_alert(
            _EscalationView(escalation_id, type, summary, options), ops_link,
        )
        if message_ids:
            await session.execute(
                text("UPDATE escalations SET telegram_message_ids = CAST(:ids AS jsonb) WHERE id = :id"),
                {"ids": json.dumps(message_ids), "id": escalation_id},
            )
    except Exception:
        # A failed alert must never fail the escalation itself -- the row
        # (and whatever automatic fallback/default behaviour depends on it)
        # still has to exist even if nobody got pinged about it.
        logger.exception("raise_escalation: failed to send Telegram alert for escalation %s", escalation_id)

    return escalation_id
