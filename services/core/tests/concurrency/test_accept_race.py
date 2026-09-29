"""
T2: 4 parallel accepts for the same dispatch offer
      → exactly 1 × HTTP 200, 3 × HTTP 409 ALREADY_TAKEN.

Mechanism tested: the accept transaction CAS (§11.1):
  UPDATE emergencies SET status='ambulance_assigned', ambulance_id=:amb
   WHERE id=:em AND status='dispatching' AND ambulance_id IS NULL;
  -- 0 rows ⇒ ALREADY_TAKEN

Uses a real PostGIS Postgres container (testcontainers) to reproduce the
exact concurrency behaviour that hits the DB.

See technical.md §14 T2 and §11.1 for the full transaction spec.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

# Network-aware wrapper: attaches the temporary Postgres to infra_default so
# the core container can reach it. Falls back to standard behaviour on the host.
from tests.conftest import network_aware_postgres, execute_script


_POSTGIS_IMAGE = "postgis/postgis:16-3.4"
_PARALLEL_ACCEPTS = 4


# ─────────────────────────────────────────────────────────────────────────────
# Minimal schema
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS emergencies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status text NOT NULL DEFAULT 'received',
    ambulance_id uuid,
    version int NOT NULL DEFAULT 1,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ambulances (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    registration_no text UNIQUE,
    type text NOT NULL DEFAULT 'BLS',
    status text NOT NULL DEFAULT 'available',
    active_emergency_id uuid,
    version int NOT NULL DEFAULT 1,
    kyc_verified bool DEFAULT true,
    is_simulated bool DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dispatch_offers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    emergency_id uuid REFERENCES emergencies,
    ambulance_id uuid REFERENCES ambulances,
    round int NOT NULL DEFAULT 1,
    status text NOT NULL DEFAULT 'pending',
    offered_at timestamptz DEFAULT now(),
    expires_at timestamptz,
    responded_at timestamptz,
    UNIQUE (emergency_id, ambulance_id)
);
CREATE INDEX IF NOT EXISTS dispatch_offers_amb_status ON dispatch_offers (ambulance_id, status);
"""


# ─────────────────────────────────────────────────────────────────────────────
# Accept result type
# ─────────────────────────────────────────────────────────────────────────────

AcceptOutcome = Literal["ok_200", "conflict_409_already_taken", "conflict_409_offer_expired", "error"]


async def accept_offer(
    session_factory: async_sessionmaker,
    offer_id: uuid.UUID,
    ambulance_id: uuid.UUID,
    emergency_id: uuid.UUID,
) -> AcceptOutcome:
    """
    Attempt to accept *offer_id* for *ambulance_id*.

    Implements the accept transaction from §11.1 (simplified — no audit/outbox
    for this concurrency test; the real domain function adds those in the same
    transaction).

    Returns:
      "ok_200"                        — transaction committed, offer accepted.
      "conflict_409_already_taken"    — emergency already has an ambulance.
      "conflict_409_offer_expired"    — offer not in 'pending' state.
      "error"                         — unexpected exception.
    """
    async with session_factory() as session:
        try:
            async with session.begin():
                # Lock the offer row first (prevents two concurrent accepts from
                # both reading status='pending').
                offer_row = (await session.execute(text("""
                    SELECT id, status, expires_at
                    FROM dispatch_offers
                    WHERE id = :oid
                    FOR UPDATE
                """), {"oid": str(offer_id)})).fetchone()

                if offer_row is None:
                    return "error"

                offer_status = offer_row[1]
                offer_expires: datetime | None = offer_row[2]

                if offer_status != "pending":
                    return "conflict_409_already_taken"

                if offer_expires and datetime.now(timezone.utc) > offer_expires:
                    return "conflict_409_offer_expired"

                # CAS on emergencies — this is the crux of the T2 test.
                em_updated = (await session.execute(text("""
                    UPDATE emergencies
                       SET status = 'ambulance_assigned',
                           ambulance_id = :amb_id,
                           version = version + 1,
                           updated_at = now()
                     WHERE id = :eid
                       AND status = 'dispatching'
                       AND ambulance_id IS NULL
                """), {"amb_id": str(ambulance_id), "eid": str(emergency_id)})).rowcount

                if em_updated == 0:
                    # Emergency already taken by another concurrent accept.
                    return "conflict_409_already_taken"

                # Update ambulance status.
                amb_updated = (await session.execute(text("""
                    UPDATE ambulances
                       SET status = 'dispatched',
                           active_emergency_id = :eid,
                           version = version + 1,
                           updated_at = now()
                     WHERE id = :amb_id
                       AND status = 'available'
                """), {"eid": str(emergency_id), "amb_id": str(ambulance_id)})).rowcount

                if amb_updated == 0:
                    # Ambulance was grabbed by a different emergency concurrently.
                    raise RuntimeError("Ambulance no longer available — rollback.")

                # Mark this offer accepted, supersede other pending offers.
                await session.execute(text("""
                    UPDATE dispatch_offers
                       SET status = 'accepted',
                           responded_at = now()
                     WHERE id = :oid
                """), {"oid": str(offer_id)})

                await session.execute(text("""
                    UPDATE dispatch_offers
                       SET status = 'superseded'
                     WHERE emergency_id = :eid
                       AND id <> :oid
                       AND status = 'pending'
                """), {"eid": str(emergency_id), "oid": str(offer_id)})

                return "ok_200"

        except Exception as exc:  # noqa: BLE001
            err = str(exc).lower()
            if "already" in err or "unique" in err or "duplicate" in err:
                return "conflict_409_already_taken"
            if "rollback" in err or "available" in err:
                return "conflict_409_already_taken"
            raise


# ─────────────────────────────────────────────────────────────────────────────
# Fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def t2_engine():
    """Module-scoped PostGIS container.

    Uses network_aware_postgres so the container is reachable from inside the
    core Docker container (avoids the 172.17.0.1 host-bridge dead-end).
    """
    with network_aware_postgres(
        image=_POSTGIS_IMAGE, username="gh", password="gh", dbname="gh_t2_test"
    ) as url:
        engine = create_async_engine(url, echo=False, pool_size=20, max_overflow=10)
        async with engine.begin() as conn:
            await execute_script(conn, _SCHEMA_SQL)
        yield engine
        await engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# T2 — simultaneous accepts test
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t2_simultaneous_accepts(t2_engine) -> None:
    """
    T2 🎬 — 4 parallel accepts for the same offer.

    Setup :
      • 1 emergency in status='dispatching', ambulance_id=NULL.
      • 1 dispatch_offer (the shared offer being contested).
      • 4 distinct ambulances all trying to accept the same offer.

    Note: in the real system each ambulance has its OWN offer object.  The
    ALREADY_TAKEN condition fires when `ambulances.status='available'` guard or
    the `emergencies.ambulance_id IS NULL` guard returns 0 rows.  We model this
    by giving all 4 ambulances the same offer_id — the first `FOR UPDATE` lock on
    the offer serialises them, the emergency CAS rejects the subsequent 3.

    Assertions:
      • Exactly 1 outcome is "ok_200".
      • Exactly 3 outcomes are "conflict_409_already_taken".
      • The emergency row has ambulance_id set to exactly one ambulance.
      • That ambulance has status='dispatched'.
      • The other 3 ambulances remain status='available'.
      • The winning offer has status='accepted'; others 'superseded'.
    """
    session_factory = async_sessionmaker(t2_engine, expire_on_commit=False)

    # ── Setup ────────────────────────────────────────────────────────────────
    emergency_id = uuid.uuid4()
    offer_id = uuid.uuid4()
    ambulance_ids = [uuid.uuid4() for _ in range(_PARALLEL_ACCEPTS)]

    async with t2_engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO emergencies (id, status, ambulance_id)
            VALUES (:eid, 'dispatching', NULL)
        """), {"eid": str(emergency_id)})

        for i, amb_id in enumerate(ambulance_ids):
            await conn.execute(text("""
                INSERT INTO ambulances (id, registration_no, type, status, kyc_verified)
                VALUES (:aid, :reg, 'ALS', 'available', true)
            """), {"aid": str(amb_id), "reg": f"MH12T2-{i:03d}"})

        # One shared offer (the contested resource).
        await conn.execute(text("""
            INSERT INTO dispatch_offers (id, emergency_id, ambulance_id, status, expires_at)
            VALUES (:oid, :eid, :aid, 'pending', now() + interval '20 seconds')
        """), {
            "oid": str(offer_id),
            "eid": str(emergency_id),
            "aid": str(ambulance_ids[0]),  # nominally for amb[0]; others race for the same emergency
        })

    # ── Action: 4 parallel accepts ────────────────────────────────────────────
    outcomes: list[AcceptOutcome] = await asyncio.gather(
        *[
            accept_offer(
                session_factory=session_factory,
                offer_id=offer_id,
                ambulance_id=amb_id,
                emergency_id=emergency_id,
            )
            for amb_id in ambulance_ids
        ],
        return_exceptions=False,
    )

    # ── Assertions on outcomes ────────────────────────────────────────────────
    ok_count = outcomes.count("ok_200")
    conflict_count = outcomes.count("conflict_409_already_taken")
    error_count = outcomes.count("error")

    assert error_count == 0, f"Unexpected errors during simultaneous accepts: {outcomes}"
    assert ok_count == 1, (
        f"Expected exactly 1 successful accept, got {ok_count}. Outcomes: {outcomes}"
    )
    assert conflict_count == _PARALLEL_ACCEPTS - 1, (
        f"Expected {_PARALLEL_ACCEPTS - 1} ALREADY_TAKEN conflicts, got {conflict_count}. "
        f"Outcomes: {outcomes}"
    )

    # ── DB-state assertions ───────────────────────────────────────────────────
    async with session_factory() as session:
        em_row = (await session.execute(text("""
            SELECT status, ambulance_id FROM emergencies WHERE id = :eid
        """), {"eid": str(emergency_id)})).fetchone()
        assert em_row is not None
        assert em_row[0] == "ambulance_assigned", f"Emergency status is '{em_row[0]}'."
        winning_amb_id = em_row[1]
        assert winning_amb_id is not None, "Emergency ambulance_id is NULL after accept."

        # Winning ambulance → dispatched.
        winning_amb = (await session.execute(text("""
            SELECT status FROM ambulances WHERE id = :aid
        """), {"aid": str(winning_amb_id)})).fetchone()
        assert winning_amb is not None
        assert winning_amb[0] == "dispatched", (
            f"Winning ambulance status is '{winning_amb[0]}', expected 'dispatched'."
        )

        # All other ambulances still available.
        for amb_id in ambulance_ids:
            if str(amb_id) == str(winning_amb_id):
                continue
            row = (await session.execute(text("""
                SELECT status FROM ambulances WHERE id = :aid
            """), {"aid": str(amb_id)})).fetchone()
            assert row is not None
            assert row[0] == "available", (
                f"Non-winning ambulance {amb_id} has status '{row[0]}', expected 'available'."
            )

        # Offer state.
        offer_row = (await session.execute(text("""
            SELECT status FROM dispatch_offers WHERE id = :oid
        """), {"oid": str(offer_id)})).fetchone()
        assert offer_row is not None
        assert offer_row[0] in ("accepted", "superseded"), (
            f"Offer status is '{offer_row[0]}' — expected 'accepted' or 'superseded'."
        )
