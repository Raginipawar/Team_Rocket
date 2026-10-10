"""Safety net sweeper for missed timers (runs every 5s, leader only)."""
from datetime import datetime, timezone, timedelta
from app.db.engine import AsyncSessionLocal
from sqlalchemy import select
from app.db.models import (
    DispatchOffer, HospitalRequest, Reservation, 
    Ambulance, Escalation, Handoff
) # type: ignore
from app.domain.reservations import timeout_hospital_request
from app.db.repos.reservations import release_reservation

SIGNAL_LOST_SEC = 300
OFFLOAD_DELAY_ALERT_MIN = 30

async def sweep(ctx: dict) -> None:
    """Safety net for missed timers (technical.md §10.2)."""
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        
        # 1. Expired offers
        stmt_offers = select(DispatchOffer).where(
            DispatchOffer.status == 'PENDING',
            DispatchOffer.expires_at < now
        )
        for offer in (await db.execute(stmt_offers)).scalars():
            offer.status = 'expired'
            
        # 2. Hospital request timeouts (older than 5 min)
        timeout_threshold = now - timedelta(minutes=5)
        stmt_req = select(HospitalRequest).where(
            HospitalRequest.status == 'PENDING',
            HospitalRequest.created_at < timeout_threshold
        )
        for req in (await db.execute(stmt_req)).scalars():
            await timeout_hospital_request(db, req.id)
            
        # 3. Hold expiries
        stmt_res = select(Reservation).where(
            Reservation.status == 'held'
        )
        for res in (await db.execute(stmt_res)).scalars():
            expires = getattr(res, 'expires_at', None)
            if expires:
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if expires < now:
                    await release_reservation(db, res.id, 'expired')
            else:
                created = res.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created < timeout_threshold:
                    await release_reservation(db, res.id, 'expired')

        # 4. Signal-lost detection
        signal_lost_threshold = now - timedelta(seconds=SIGNAL_LOST_SEC)
        stmt_amb = select(Ambulance).where(
            Ambulance.status.in_(['DISPATCHED', 'EN_ROUTE', 'ON_SCENE', 'TRANSPORTING']),
            Ambulance.updated_at < signal_lost_threshold
        )
        for amb in (await db.execute(stmt_amb)).scalars():
            amb.status = 'SIGNAL_LOST'

        redis = ctx.get('redis')
        if redis:
            # 5. Escalation repeat
            stmt_esc_rep = select(Escalation).where(
                Escalation.status.in_(['open', 'claimed']),
                Escalation.repeat_at < now
            )
            for esc in (await db.execute(stmt_esc_rep)).scalars():
                await redis.enqueue_job('job_escalation_repeat', esc.id)
                esc.repeat_at = None

            # 6. Escalation default
            stmt_esc_def = select(Escalation).where(
                Escalation.status.in_(['open', 'claimed']),
                Escalation.default_at < now
            )
            for esc in (await db.execute(stmt_esc_def)).scalars():
                await redis.enqueue_job('job_escalation_default', esc.id)
                esc.default_at = None

        # 7. Offload delay alert
        delay_threshold = now - timedelta(minutes=OFFLOAD_DELAY_ALERT_MIN)
        stmt_handoff = select(Handoff).where(
            Handoff.status == 'IN_PROGRESS',
            Handoff.created_at < delay_threshold
        )
        for handoff in (await db.execute(stmt_handoff)).scalars():
            handoff.status = 'DELAYED'
            
        await db.commit()
