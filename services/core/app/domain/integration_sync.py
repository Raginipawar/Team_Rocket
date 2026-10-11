"""Real API-integration sync: the settings page (hospital.py's /integration
PATCH) only ever stored the endpoint/key -- nothing ever called it. This
is what actually fetches from a hospital's own system and applies it.

Deliberately scoped to hospital_resources (ventilators, blood units,
scanners, etc.) -- countable, versioned, safe to overwrite wholesale from
an external count. Individual rooms (er_bed/icu_bed/...) are NOT touched:
each room is a specific physical bed that may have a real patient in it
right now, and blindly flipping N of them to match an external "X beds
free" count risks silently overwriting a real occupied/reserved room.
That reconciliation needs a real strategy (which N rooms, never touching
ones mid-handoff) this hackathon doesn't have time to get right safely --
better to leave rooms manual-only than guess wrong with patient safety
on the line.

Expected external API contract (GET, Authorization: Bearer <api_key>):
    {"resources": [{"type": "ventilator", "available": 3, "total": 5}, ...]}
`type` must match this hospital's existing hospital_resources.type rows
(seeded set: ventilator, cath_lab, ct_scanner, mri, defibrillator,
blood_o_neg/o_pos/a_pos/b_pos/ab_pos, dialysis, operating_theatre) --
unknown types are reported back, not silently dropped or auto-created."""

import logging

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("integration_sync")
SYNC_TIMEOUT_SEC = 10.0


class SyncError(Exception):
    pass


async def sync_hospital_from_api(session: AsyncSession, hospital_id: str) -> dict:
    row = (await session.execute(
        text("SELECT integration_mode, integration_endpoint_url, integration_api_key FROM hospitals WHERE id = :id"),
        {"id": hospital_id},
    )).mappings().first()
    if row is None:
        raise SyncError("hospital not found")
    if row["integration_mode"] != "api" or not row["integration_endpoint_url"]:
        raise SyncError("API integration is not enabled for this hospital")

    headers = {"Accept": "application/json"}
    if row["integration_api_key"]:
        # Supabase's PostgREST (the realistic case: a hospital's own table,
        # not a hand-built API) requires the key on BOTH headers -- apikey
        # always, Authorization for RLS policies that check auth.role().
        # A non-Supabase endpoint just ignores the extra header.
        headers["Authorization"] = f"Bearer {row['integration_api_key']}"
        headers["apikey"] = row["integration_api_key"]

    try:
        async with httpx.AsyncClient(timeout=SYNC_TIMEOUT_SEC) as client:
            resp = await client.get(row["integration_endpoint_url"], headers=headers)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as e:
        raise SyncError(f"could not reach the configured endpoint: {e}") from e
    except ValueError as e:
        raise SyncError(f"endpoint did not return valid JSON: {e}") from e

    # Accept either a bare array (Supabase/PostgREST's own response shape
    # for a table -- GET .../hospital_capacity?select=... returns rows
    # directly, not wrapped) or {"resources": [...]} for a hand-built API.
    items = payload if isinstance(payload, list) else (payload.get("resources") if isinstance(payload, dict) else None)
    if not isinstance(items, list):
        raise SyncError('expected a JSON array of rows, or {"resources": [{"type": ..., "available": ..., "total": ...}, ...]}')

    known_types = {r["type"] for r in (await session.execute(
        text("SELECT type FROM hospital_resources WHERE hospital_id = :id"), {"id": hospital_id},
    )).mappings().all()}

    updated, skipped = [], []
    for item in items:
        rtype = item.get("type") if isinstance(item, dict) else None
        available = item.get("available") if isinstance(item, dict) else None
        if rtype not in known_types or not isinstance(available, int) or available < 0:
            skipped.append(item)
            continue
        total = item.get("total")
        if isinstance(total, int) and total >= 0:
            await session.execute(
                text("UPDATE hospital_resources SET available = :avail, total = :total, "
                     "reported_at = now(), version = version + 1 WHERE hospital_id = :hid AND type = :type"),
                {"avail": available, "total": total, "hid": hospital_id, "type": rtype},
            )
        else:
            await session.execute(
                text("UPDATE hospital_resources SET available = LEAST(:avail, total), "
                     "reported_at = now(), version = version + 1 WHERE hospital_id = :hid AND type = :type"),
                {"avail": available, "hid": hospital_id, "type": rtype},
            )
        updated.append(rtype)

    # A successful sync is as real a "yes, these numbers are current" signal
    # as a manual Confirm availability tap -- dispatch's freshness check
    # (hospital.py's _calculate_freshness) shouldn't need a human to also
    # separately confirm right after an API sync just updated the same data.
    await session.execute(
        text("UPDATE hospitals SET integration_last_synced_at = now(), last_confirmed_at = now() WHERE id = :id"),
        {"id": hospital_id},
    )
    return {"updated": updated, "skipped": skipped}
