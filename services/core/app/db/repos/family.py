"""Family space: a patient's own shareable code, and one-directional
"I watch them" connections made by entering someone else's code. New
feature -- didn't exist in any form before."""
import random
import string
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _generate_code() -> str:
    # 6 chars, no 0/O/1/I to avoid read-aloud/typo confusion -- this is
    # meant to be spoken over a phone call or texted to a family member.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(6))


async def get_or_create_family_code(session: AsyncSession, user_id: str) -> str:
    existing = (await session.execute(
        text("SELECT family_code FROM health_profiles WHERE user_id = :uid"), {"uid": user_id}
    )).scalar_one_or_none()
    if existing:
        return existing

    # Ensure a health_profiles row exists at all (same as patient.py's
    # get_or_create_health_profile -- a brand new user may not have one yet).
    await session.execute(
        text("INSERT INTO health_profiles (user_id, allergies, conditions, medications, version) "
             "VALUES (:uid, '{}', '{}', '{}', 1) ON CONFLICT (user_id) DO NOTHING"),
        {"uid": user_id},
    )
    for _ in range(10):  # astronomically unlikely to collide twice, let alone 10x
        code = _generate_code()
        row = (await session.execute(
            text("UPDATE health_profiles SET family_code = :code WHERE user_id = :uid AND family_code IS NULL RETURNING family_code"),
            {"code": code, "uid": user_id},
        )).scalar_one_or_none()
        if row:
            return row
        # someone else grabbed that code between generate and write -- retry
    raise RuntimeError("could not allocate a unique family code")


class CodeNotFound(Exception):
    pass


class CannotWatchSelf(Exception):
    pass


async def connect_by_code(session: AsyncSession, watcher_user_id: str, code: str) -> dict:
    watched = (await session.execute(
        text("SELECT hp.user_id, u.name, u.phone FROM health_profiles hp JOIN users u ON u.id = hp.user_id "
             "WHERE hp.family_code = :code"),
        {"code": code.strip().upper()},
    )).mappings().first()
    if not watched:
        raise CodeNotFound()
    if str(watched["user_id"]) == str(watcher_user_id):
        raise CannotWatchSelf()

    await session.execute(
        text("INSERT INTO family_connections (watcher_user_id, watched_user_id) VALUES (:w, :t) "
             "ON CONFLICT (watcher_user_id, watched_user_id) DO NOTHING"),
        {"w": watcher_user_id, "t": watched["user_id"]},
    )
    return {"user_id": str(watched["user_id"]), "name": watched["name"], "phone": watched["phone"]}


async def list_watched(session: AsyncSession, watcher_user_id: str) -> list[dict]:
    rows = (await session.execute(
        text("""
            SELECT u.id, u.name, u.phone, hp.blood_group,
                   (SELECT em.status FROM emergencies em WHERE em.caller_user_id = u.id
                    AND em.status NOT IN ('handed_off','cancelled','closed','merged_duplicate','refused_transport')
                    ORDER BY em.received_at DESC LIMIT 1) AS active_emergency_status
            FROM family_connections fc
            JOIN users u ON u.id = fc.watched_user_id
            LEFT JOIN health_profiles hp ON hp.user_id = u.id
            WHERE fc.watcher_user_id = :watcher
            ORDER BY fc.created_at ASC
        """),
        {"watcher": watcher_user_id},
    )).mappings().all()
    return [dict(r) for r in rows]


class NotConnected(Exception):
    pass


async def get_watched_health(session: AsyncSession, watcher_user_id: str, watched_user_id: str) -> dict:
    connected = (await session.execute(
        text("SELECT 1 FROM family_connections WHERE watcher_user_id = :w AND watched_user_id = :t"),
        {"w": watcher_user_id, "t": watched_user_id},
    )).scalar_one_or_none()
    if not connected:
        raise NotConnected()
    row = (await session.execute(
        text("""
            SELECT u.name, hp.blood_group, hp.allergies, hp.conditions, hp.medications, hp.home_address
            FROM users u LEFT JOIN health_profiles hp ON hp.user_id = u.id
            WHERE u.id = :uid
        """),
        {"uid": watched_user_id},
    )).mappings().first()
    return dict(row) if row else {}


async def get_watched_contact(session: AsyncSession, watcher_user_id: str, watched_user_id: str) -> dict:
    connected = (await session.execute(
        text("SELECT 1 FROM family_connections WHERE watcher_user_id = :w AND watched_user_id = :t"),
        {"w": watcher_user_id, "t": watched_user_id},
    )).scalar_one_or_none()
    if not connected:
        raise NotConnected()
    row = (await session.execute(
        text("SELECT u.name, u.phone, hp.home_address FROM users u LEFT JOIN health_profiles hp ON hp.user_id = u.id WHERE u.id = :uid"),
        {"uid": watched_user_id},
    )).mappings().first()
    return dict(row) if row else {}
