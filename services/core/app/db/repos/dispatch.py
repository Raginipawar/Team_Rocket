"""A's file (work-distribution.md §2.2). Offer creation + the accept
transaction, transcribed exactly from technical.md §11.1 (including the
comment on each UPDATE explaining what a zero-row result means)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

OFFER_EXPIRY_SEC = 45


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
            " clock_timestamp(), clock_timestamp() + make_interval(secs => :expiry_sec)) "
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


async def list_pending_offers(session: AsyncSession, ambulance_id: str) -> list[dict]:
    """GET /ambulance/offers (lib/ambulance.ts fetchOffers()). Never existed
    on the real backend -- fetchOffers() already tolerated a 404 gracefully
    ("router not live yet: offers still arrive over WS"), but the ambulance
    app ALSO polls this every 3-15s as a backup/resync alongside the WS
    push, and that graceful-404-to-[] fallback was overwriting the real
    offer React Query had just received over WS moments earlier -- a real
    live offer disappearing from the screen a few seconds after arriving,
    not a 20s-expiry issue. Real rows now, so the poll can never wipe it."""
    rows = (await session.execute(
        text("""
            SELECT off.id AS offer_id, off.emergency_id, off.expires_at, off.predicted_eta_sec AS eta_sec,
                   em.final_acuity, em.ai_acuity, em.final_facility, em.ai_facility,
                   ST_Y(em.location::geometry) AS pickup_lat, ST_X(em.location::geometry) AS pickup_lng,
                   em.location_accuracy_m, em.landmark_text
            FROM dispatch_offers off
            JOIN emergencies em ON em.id = off.emergency_id
            WHERE off.ambulance_id = :ambulance_id AND off.status = 'pending' AND off.expires_at > now()
            ORDER BY off.offered_at DESC
        """),
        {"ambulance_id": ambulance_id},
    )).mappings().all()
    return [
        {
            "offer_id": str(r["offer_id"]), "emergency_id": str(r["emergency_id"]),
            "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
            "pickup_lat": r["pickup_lat"], "pickup_lng": r["pickup_lng"],
            "eta_sec": r["eta_sec"], "acuity": r["final_acuity"] or r["ai_acuity"] or "urgent",
            "facility": r["final_facility"] or r["ai_facility"] or "general",
        }
        for r in rows
    ]


async def get_offer(session: AsyncSession, offer_id: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, emergency_id, ambulance_id, status, expires_at FROM dispatch_offers WHERE id = :id"),
        {"id": offer_id},
    )).mappings().first()
    return dict(row) if row else None


async def decline_offer(session: AsyncSession, *, offer_id: str, paramedic_ambulance_id: str) -> dict:
    """Mark a pending offer declined. No immediate re-dispatch here --
    emergency.status stays 'dispatching', so the existing 30s round loop
    (domain/dispatch.py's _continue_rounds) picks this ambulance up as
    already-excluded and keeps offering others on schedule."""
    row = (await session.execute(
        text(
            "UPDATE dispatch_offers SET status = 'declined', responded_at = now() "
            "WHERE id = :id AND ambulance_id = :ambulance_id AND status = 'pending' "
            "RETURNING id, emergency_id, ambulance_id"
        ),
        {"id": offer_id, "ambulance_id": paramedic_ambulance_id},
    )).mappings().first()
    if not row:
        raise OfferNotAvailable()
    return dict(row)


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
