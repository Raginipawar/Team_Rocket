"""Family space: real group membership, not a directional "watch" graph.
One family per user, enforced at the DB level (family_members.user_id is
UNIQUE) so a race between two near-simultaneous create/join calls for the
same user can't produce two memberships -- the second INSERT just fails
with a unique-violation, caught and turned into AlreadyInFamily."""
import random
import string
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def _generate_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(6))


class AlreadyInFamily(Exception):
    pass


class CodeNotFound(Exception):
    pass


class NotInFamily(Exception):
    pass


async def get_my_family(session: AsyncSession, user_id: str) -> dict | None:
    fam = (await session.execute(
        text("""
            SELECT f.id, f.code, f.name, f.owner_user_id
            FROM families f JOIN family_members fm ON fm.family_id = f.id
            WHERE fm.user_id = :uid
        """), {"uid": user_id},
    )).mappings().first()
    if not fam:
        return None
    members = (await session.execute(
        text("""
            SELECT u.id, u.name, u.phone, hp.blood_group,
                   (SELECT em.status FROM emergencies em WHERE em.caller_user_id = u.id
                    AND em.status NOT IN ('handed_off','cancelled','closed','merged_duplicate','refused_transport')
                    ORDER BY em.received_at DESC LIMIT 1) AS active_emergency_status,
                   u.last_location_at,
                   EXTRACT(EPOCH FROM (now() - u.last_location_at))::float8 AS location_age_sec
            FROM family_members fm
            JOIN users u ON u.id = fm.user_id
            LEFT JOIN health_profiles hp ON hp.user_id = u.id
            WHERE fm.family_id = :fid
            ORDER BY fm.created_at ASC
        """), {"fid": fam["id"]},
    )).mappings().all()
    return {
        "family_id": str(fam["id"]), "code": fam["code"], "name": fam["name"],
        "is_owner": str(fam["owner_user_id"]) == str(user_id),
        "members": [dict(m) for m in members],
    }


async def create_family(session: AsyncSession, user_id: str, name: str | None = None) -> dict:
    # Caller commits (same convention as every other repo in this module) --
    # this only commits internally on the retryable code-collision path,
    # since that one genuinely needs a fresh transaction to try again.
    for _ in range(10):
        code = _generate_code()
        try:
            async with session.begin_nested():
                fam = (await session.execute(
                    text("INSERT INTO families (code, name, owner_user_id) VALUES (:code, :name, :uid) RETURNING id"),
                    {"code": code, "name": name, "uid": user_id},
                )).mappings().first()
                await session.execute(
                    text("INSERT INTO family_members (family_id, user_id) VALUES (:fid, :uid)"),
                    {"fid": fam["id"], "uid": user_id},
                )
            return await get_my_family(session, user_id)
        except IntegrityError as e:
            if "families_code_key" in str(e.orig):
                continue  # code collision, retry with a new one
            raise AlreadyInFamily()  # family_members.user_id unique violation
    raise RuntimeError("could not allocate a unique family code")


async def join_family(session: AsyncSession, user_id: str, code: str) -> dict:
    fam = (await session.execute(
        text("SELECT id FROM families WHERE code = :code"), {"code": code.strip().upper()},
    )).mappings().first()
    if not fam:
        raise CodeNotFound()
    try:
        async with session.begin_nested():
            await session.execute(
                text("INSERT INTO family_members (family_id, user_id) VALUES (:fid, :uid)"),
                {"fid": fam["id"], "uid": user_id},
            )
    except IntegrityError:
        raise AlreadyInFamily()
    return await get_my_family(session, user_id)


async def _require_same_family(session: AsyncSession, user_id: str, other_user_id: str) -> None:
    row = (await session.execute(
        text("""
            SELECT 1 FROM family_members a JOIN family_members b ON a.family_id = b.family_id
            WHERE a.user_id = :u AND b.user_id = :o
        """), {"u": user_id, "o": other_user_id},
    )).scalar_one_or_none()
    if not row:
        raise NotInFamily()


async def get_member_health(session: AsyncSession, user_id: str, member_user_id: str) -> dict:
    await _require_same_family(session, user_id, member_user_id)
    row = (await session.execute(
        text("""
            SELECT u.name, hp.blood_group, hp.allergies, hp.conditions, hp.medications, hp.home_address
            FROM users u LEFT JOIN health_profiles hp ON hp.user_id = u.id
            WHERE u.id = :uid
        """), {"uid": member_user_id},
    )).mappings().first()
    return dict(row) if row else {}


async def get_member_contact(session: AsyncSession, user_id: str, member_user_id: str) -> dict:
    await _require_same_family(session, user_id, member_user_id)
    row = (await session.execute(
        text("SELECT u.name, u.phone, hp.home_address FROM users u LEFT JOIN health_profiles hp ON hp.user_id = u.id WHERE u.id = :uid"),
        {"uid": member_user_id},
    )).mappings().first()
    return dict(row) if row else {}
