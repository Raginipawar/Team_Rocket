"""Patient + family push notifications for real status-change events
(technical.md §12.3). Nothing previously called send_push() for the
patient at all -- only the paramedic-facing "new offer" notification
existed. A caller whose phone is locked/backgrounded had no way to know
their ambulance was assigned, a hospital confirmed, or the ambulance had
arrived, without having the app open and polling. Family members get the
exact same notifications -- the same real "watch this person" membership
Family Space already uses for everything else."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.push.sender import send_push


async def notify_patient_and_family(
    session: AsyncSession, emergency_id: str, title: str, body: str, data: dict | None = None,
) -> None:
    row = (await session.execute(
        text("SELECT caller_user_id FROM emergencies WHERE id = :id"), {"id": emergency_id},
    )).mappings().first()
    if not row or not row["caller_user_id"]:
        return
    caller_id: UUID = row["caller_user_id"]
    payload = {**(data or {}), "emergency_id": str(emergency_id)}

    await send_push(caller_id, title, body, payload)

    family_rows = (await session.execute(
        text("""
            SELECT fm2.user_id FROM family_members fm1
            JOIN family_members fm2 ON fm1.family_id = fm2.family_id
            WHERE fm1.user_id = :uid AND fm2.user_id != :uid
        """),
        {"uid": str(caller_id)},
    )).mappings().all()
    for r in family_rows:
        await send_push(r["user_id"], title, body, payload)
