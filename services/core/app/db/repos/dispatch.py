"""A's file (work-distribution.md §2.2). Offer creation + the accept
transaction, transcribed exactly from technical.md §11.1 (including the
comment on each UPDATE explaining what a zero-row result means)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

OFFER_EXPIRY_SEC = 20


class AlreadyTaken(Exception):
    pass


class AmbulanceBusy(Exception):
    pass


class OfferNotAvailable(Exception):
    pass


async def create_offer(
    session: AsyncSession, *, emergency_id: str, ambulance_id: str, round: int,
    predicted_accept_prob: float, predicted_eta_sec: int, rank: int,
) -> dict:
    row = (await session.execute(
        text(
            "INSERT INTO dispatch_offers "
            "(emergency_id, ambulance_id, round, status, predicted_accept_prob, predicted_eta_sec, rank, "
            " offered_at, expires_at) "
            "VALUES (:emergency_id, :ambulance_id, :round, 'pending', :prob, :eta_sec, :rank, "
            " now(), now() + make_interval(secs => :expiry_sec)) "
            "RETURNING id, emergency_id, ambulance_id, round, expires_at"
        ),
        {
            "emergency_id": emergency_id, "ambulance_id": ambulance_id, "round": round,
            "prob": predicted_accept_prob, "eta_sec": predicted_eta_sec, "rank": rank,
            "expiry_sec": OFFER_EXPIRY_SEC,
        },
    )).mappings().first()
    return dict(row)


async def already_offered_ambulance_ids(session: AsyncSession, emergency_id: str) -> list[str]:
    rows = (await session.execute(
        text("SELECT ambulance_id FROM dispatch_offers WHERE emergency_id = :id"),
        {"id": emergency_id},
    )).scalars().all()
    return [str(r) for r in rows]


async def get_offer(session: AsyncSession, offer_id: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, emergency_id, ambulance_id, status, expires_at FROM dispatch_offers WHERE id = :id"),
        {"id": offer_id},
    )).mappings().first()
    return dict(row) if row else None


async def accept_offer(session: AsyncSession, *, offer_id: str, paramedic_ambulance_id: str) -> dict:
    """technical.md §11.1 accept transaction, verbatim. Caller (api/v1/offers.py)
    wraps this in try/except for AlreadyTaken/AmbulanceBusy/OfferNotAvailable
    and must call session.commit() itself -- this function does not commit,
    so the audit + outbox writes the caller adds land in the same transaction."""

    offer = (await session.execute(
        text(
            "SELECT id, emergency_id, ambulance_id, status, expires_at FROM dispatch_offers "
            "WHERE id = :id FOR UPDATE"
        ),
        {"id": offer_id},
    )).mappings().first()

    if offer is None or offer["status"] != "pending":
        raise OfferNotAvailable()
    if offer["expires_at"] is not None:
        expired = (await session.execute(text("SELECT :exp < now()"), {"exp": offer["expires_at"]})).scalar()
        if expired:
            raise OfferNotAvailable()
    if str(offer["ambulance_id"]) != str(paramedic_ambulance_id):
        raise OfferNotAvailable()

    emergency_id = offer["emergency_id"]
    ambulance_id = offer["ambulance_id"]

    em_result = await session.execute(
        text(
            "UPDATE emergencies SET status='ambulance_assigned', ambulance_id=:amb, "
            "assigned_at=now(), version=version+1 "
            "WHERE id=:em AND status='dispatching' AND ambulance_id IS NULL"
        ),
        {"amb": ambulance_id, "em": emergency_id},
    )
    if em_result.rowcount == 0:
        raise AlreadyTaken()

    amb_result = await session.execute(
        text(
            "UPDATE ambulances SET status='dispatched', active_emergency_id=:em, version=version+1 "
            "WHERE id=:amb AND status='available'"
        ),
        {"em": emergency_id, "amb": ambulance_id},
    )
    if amb_result.rowcount == 0:
        raise AmbulanceBusy()

    await session.execute(
        text("UPDATE dispatch_offers SET status='accepted', responded_at=now() WHERE id=:offer"),
        {"offer": offer_id},
    )
    await session.execute(
        text(
            "UPDATE dispatch_offers SET status='superseded' "
            "WHERE emergency_id=:em AND id<>:offer AND status='pending'"
        ),
        {"em": emergency_id, "offer": offer_id},
    )
    await session.execute(
        text(
            "UPDATE dispatch_offers SET status='superseded' "
            "WHERE ambulance_id=:amb AND id<>:offer AND status='pending'"
        ),
        {"amb": ambulance_id, "offer": offer_id},
    )

    return {"emergency_id": emergency_id, "ambulance_id": ambulance_id}


async def expire_stale_offers(session: AsyncSession) -> list[dict]:
    """Sweeper-style cleanup (technical.md §10.2) -- B's real sweeper will call
    something like this every 5s; exposed here so it can be called directly
    until that framework exists."""
    rows = (await session.execute(
        text(
            "UPDATE dispatch_offers SET status='expired' "
            "WHERE status='pending' AND expires_at < now() "
            "RETURNING id, emergency_id, ambulance_id"
        )
    )).mappings().all()
    return [dict(r) for r in rows]
