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

    rooms_result = await _sync_sibling_table(
        session, hospital_id, row["integration_endpoint_url"], headers,
        table="hospital_rooms", select="code,type,status",
        sync_fn=_replace_rooms,
    )
    staff_result = await _sync_sibling_table(
        session, hospital_id, row["integration_endpoint_url"], headers,
        table="hospital_staff", select="name,specialty,on_duty",
        sync_fn=_replace_staff,
    )

    # A successful sync is as real a "yes, these numbers are current" signal
    # as a manual Confirm availability tap -- dispatch's freshness check
    # (hospital.py's _calculate_freshness) shouldn't need a human to also
    # separately confirm right after an API sync just updated the same data.
    await session.execute(
        text("UPDATE hospitals SET integration_last_synced_at = now(), last_confirmed_at = now() WHERE id = :id"),
        {"id": hospital_id},
    )
    return {"updated": updated, "skipped": skipped, "rooms": rooms_result, "staff": staff_result}


def _sibling_url(capacity_url: str, table: str, select: str) -> str:
    base = capacity_url.split("/rest/v1/")[0].rstrip("/")
    return f"{base}/rest/v1/{table}?select={select}"


async def _sync_sibling_table(session, hospital_id, capacity_url, headers, *, table, select, sync_fn) -> dict:
    # Rooms/staff are optional extensions of the same connection -- a
    # hospital that only set up hospital_capacity (resources) shouldn't
    # have its whole sync fail because hospital_rooms doesn't exist yet.
    url = _sibling_url(capacity_url, table, select)
    try:
        async with httpx.AsyncClient(timeout=SYNC_TIMEOUT_SEC) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                return {"skipped": f"{table} table not found at {url}"}
            resp.raise_for_status()
            items = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        return {"error": str(e)}
    if not isinstance(items, list):
        return {"error": "expected a JSON array of rows"}
    return await sync_fn(session, hospital_id, items)


async def _replace_rooms(session: AsyncSession, hospital_id: str, items: list) -> dict:
    valid_statuses = {"free", "occupied", "reserved", "cleaning", "out_of_service"}
    codes = []
    for item in items:
        if not isinstance(item, dict) or not item.get("code") or item.get("status") not in valid_statuses:
            continue
        codes.append(item["code"])
        await session.execute(text("""
            INSERT INTO rooms (hospital_id, code, type, status) VALUES (:hid, :code, :type, :status)
            ON CONFLICT (hospital_id, code) DO UPDATE SET type = :type, status = :status
        """), {"hid": hospital_id, "code": item["code"], "type": item.get("type", "er_bed"), "status": item["status"]})
    # Full replace, demo-appropriate: a room no longer listed in the
    # hospital's own table is one they removed there, not one we should
    # keep showing. (A real deployment with live patient occupancy would
    # need a softer reconciliation -- out of scope here, see module docstring.)
    if codes:
        await session.execute(
            text("DELETE FROM rooms WHERE hospital_id = :hid AND code != ALL(:codes)"),
            {"hid": hospital_id, "codes": codes},
        )
    return {"synced": len(codes)}


async def _replace_staff(session: AsyncSession, hospital_id: str, items: list) -> dict:
    names = []
    for item in items:
        if not isinstance(item, dict) or not item.get("name") or not item.get("specialty"):
            continue
        names.append(item["name"])
        # staff has no unique constraint on (hospital_id, name) -- a plain
        # INSERT ... ON CONFLICT DO NOTHING has no constraint to trigger on,
        # so it would just insert a fresh duplicate row every sync instead
        # of updating the existing one. WHERE NOT EXISTS first, then UPDATE.
        params = {"hid": hospital_id, "name": item["name"], "specialty": item["specialty"], "active": bool(item.get("on_duty", True))}
        await session.execute(text("""
            INSERT INTO staff (hospital_id, name, specialty, is_active)
            SELECT :hid, :name, :specialty, :active
            WHERE NOT EXISTS (SELECT 1 FROM staff WHERE hospital_id = :hid AND name = :name)
        """), params)
        await session.execute(text("""
            UPDATE staff SET specialty = :specialty, is_active = :active WHERE hospital_id = :hid AND name = :name
        """), params)
    if names:
        await session.execute(
            text("DELETE FROM staff WHERE hospital_id = :hid AND name != ALL(:names)"),
            {"hid": hospital_id, "names": names},
        )
    return {"synced": len(names)}
