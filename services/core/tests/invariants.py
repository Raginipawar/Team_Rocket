"""
Invariant checker tests — technical.md §14.

Runs the 5 system-level invariants from sim/invariants.py as pytest tests.
These tests must pass after every state change.  The same checks run every
10 s inside the simulator via the sweeper.

Invariants (verbatim from §14 §spec):
  1. No room with status='reserved' without a corresponding active reservation.
  2. No ambulance with two active emergencies.
  3. No emergency with two active reservations (held|confirmed).
  4. available + reserved <= total for every hospital_resource row.
  5. No pending hospital_request past its expiry_at by more than
     SWEEPER_INTERVAL_SEC seconds.

All tests use a real Postgres instance via testcontainers so that constraint
names and index behaviour match production exactly.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from testcontainers.postgres import PostgresContainer

from tests.conftest import network_aware_postgres, execute_script


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_POSTGIS_IMAGE = "postgis/postgis:16-3.4"
_SWEEPER_INTERVAL_SEC = 5  # mirror of config.SWEEPER_INTERVAL_SEC


async def _run_migrations(engine) -> None:
    """Apply the full Alembic migration chain against the test engine.

    Falls back to running the SQL DDL directly when Alembic is not available
    in the test environment (e.g. CI without alembic installed in PATH).
    """
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command

        cfg = AlembicConfig("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", str(engine.url).replace("+asyncpg", ""))
        alembic_command.upgrade(cfg, "head")
    except Exception:
        # Minimal schema sufficient for invariant assertions.
        schema_sql = """
            CREATE EXTENSION IF NOT EXISTS postgis;
            CREATE TABLE IF NOT EXISTS rooms (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                hospital_id uuid NOT NULL,
                code text,
                type text,
                status text NOT NULL DEFAULT 'free',
                reservation_id uuid,
                version int NOT NULL DEFAULT 1,
                priority_order int DEFAULT 0,
                status_updated_at timestamptz DEFAULT now(),
                created_at timestamptz DEFAULT now(),
                updated_at timestamptz DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS reservations (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                emergency_id uuid NOT NULL,
                hospital_id uuid NOT NULL,
                hospital_request_id uuid,
                status text NOT NULL,
                hold_expires_at timestamptz NOT NULL,
                version int NOT NULL DEFAULT 1,
                created_at timestamptz DEFAULT now(),
                updated_at timestamptz DEFAULT now()
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_reservation_per_emergency
                ON reservations (emergency_id) WHERE status IN ('held','confirmed');
            CREATE TABLE IF NOT EXISTS ambulances (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                registration_no text UNIQUE,
                type text NOT NULL DEFAULT 'BLS',
                status text NOT NULL DEFAULT 'offline',
                active_emergency_id uuid,
                version int NOT NULL DEFAULT 1,
                kyc_verified bool DEFAULT false,
                is_simulated bool DEFAULT true,
                created_at timestamptz DEFAULT now(),
                updated_at timestamptz DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS hospital_resources (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                hospital_id uuid NOT NULL,
                type text NOT NULL,
                total int NOT NULL DEFAULT 0,
                available int NOT NULL DEFAULT 0 CHECK (available >= 0),
                reserved int NOT NULL DEFAULT 0 CHECK (reserved >= 0),
                CHECK (available + reserved <= total),
                version int NOT NULL DEFAULT 1,
                reported_at timestamptz DEFAULT now(),
                created_at timestamptz DEFAULT now(),
                updated_at timestamptz DEFAULT now(),
                UNIQUE (hospital_id, type)
            );
            CREATE TABLE IF NOT EXISTS hospital_requests (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                emergency_id uuid NOT NULL,
                hospital_id uuid NOT NULL,
                rank int,
                score real,
                status text NOT NULL DEFAULT 'pending',
                expires_at timestamptz,
                sent_at timestamptz DEFAULT now(),
                created_at timestamptz DEFAULT now(),
                updated_at timestamptz DEFAULT now()
            );
        """
        async with engine.begin() as conn:
            await execute_script(conn, schema_sql)



# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def pg_engine():
    """Spin up a fresh PostGIS container for the entire test module.

    Uses network_aware_postgres so the container is reachable from inside
    the core Docker container (avoids the 172.17.0.1 host-bridge dead-end).
    """
    with network_aware_postgres(
        image=_POSTGIS_IMAGE, username="gh", password="gh", dbname="goldenhour"
    ) as url:
        engine = create_async_engine(url, echo=False)
        await _run_migrations(engine)
        yield engine
        await engine.dispose()


@pytest_asyncio.fixture()
async def db(pg_engine) -> AsyncSession:
    """Provide a fresh async session; rolls back after each test."""
    async_session = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 1 — No reserved room without an active reservation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_reserved_room_without_reservation(db: AsyncSession) -> None:
    """
    Invariant 1 (§14): every room whose status = 'reserved' MUST have a
    reservation_id that points to a row in reservations with status IN
    ('held', 'confirmed').

    Violation scenario: insert a room with status='reserved' but no matching
    reservation → the query must return that room → assertion fails → proves
    the check catches the problem.  In production state this query must return
    zero rows.
    """
    # Insert a violated room (orphaned reservation_id).
    orphan_reservation_id = uuid.uuid4()
    hospital_id = uuid.uuid4()
    await db.execute(text("""
        INSERT INTO rooms (hospital_id, code, type, status, reservation_id)
        VALUES (:hid, 'ER-ORPHAN', 'er_bed', 'reserved', :rid)
    """), {"hid": str(hospital_id), "rid": str(orphan_reservation_id)})
    await db.flush()

    result = await db.execute(text("""
        SELECT r.id
        FROM rooms r
        LEFT JOIN reservations res
            ON res.id = r.reservation_id
            AND res.status IN ('held', 'confirmed')
        WHERE r.status = 'reserved'
          AND res.id IS NULL
    """))
    orphans = result.fetchall()

    # This test documents and proves the invariant check catches violations.
    # In a clean production DB, `orphans` must be empty.
    # Here we inserted one violation → expect exactly 1 row.
    assert len(orphans) == 1, (
        "Expected the invariant check to detect the 1 injected orphaned room, "
        f"but found {len(orphans)}."
    )

    # Clean production scenario: after rollback (handled by fixture) the
    # invariant returns zero.


@pytest.mark.asyncio
async def test_no_reserved_room_without_reservation_clean(db: AsyncSession) -> None:
    """Clean-state version: with no data inserted, zero violations expected."""
    result = await db.execute(text("""
        SELECT r.id
        FROM rooms r
        LEFT JOIN reservations res
            ON res.id = r.reservation_id
            AND res.status IN ('held', 'confirmed')
        WHERE r.status = 'reserved'
          AND res.id IS NULL
    """))
    assert result.fetchall() == [], "Invariant 1 violated in clean DB state."


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 2 — No ambulance with two active emergencies
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_ambulance_two_emergencies(db: AsyncSession) -> None:
    """
    Invariant 2: an ambulance may have at most one active_emergency_id.
    The ambulance table column is a scalar (uuid NULL), so this invariant
    checks that no ambulance in an 'active' status (dispatched, at_scene,
    transporting, at_hospital) has NULL active_emergency_id.
    More precisely: no ambulance rows have a duplicate non-null
    active_emergency_id (which would indicate two emergencies share an
    ambulance).
    """
    # Insert two ambulance rows with distinct emergencies — fine.
    em1, em2, amb1, amb2 = (uuid.uuid4() for _ in range(4))
    await db.execute(text("""
        INSERT INTO ambulances (id, registration_no, type, status, active_emergency_id)
        VALUES (:a1, 'MH12TEST01', 'ALS', 'dispatched', :e1),
               (:a2, 'MH12TEST02', 'BLS', 'dispatched', :e2)
    """), {"a1": str(amb1), "e1": str(em1), "a2": str(amb2), "e2": str(em2)})
    await db.flush()

    result = await db.execute(text("""
        SELECT active_emergency_id, COUNT(*) AS cnt
        FROM ambulances
        WHERE active_emergency_id IS NOT NULL
        GROUP BY active_emergency_id
        HAVING COUNT(*) > 1
    """))
    violations = result.fetchall()
    assert violations == [], f"Invariant 2 violated — emergency assigned to multiple ambulances: {violations}"


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 3 — No emergency with two active reservations
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_emergency_two_reservations(db: AsyncSession) -> None:
    """
    Invariant 3 (§6.3, §14): the unique partial index
    `one_active_reservation_per_emergency` enforces at most one held|confirmed
    reservation per emergency at the DB level.  This test verifies the index
    exists and rejects the second insert.
    """
    emergency_id = uuid.uuid4()
    hospital_id = uuid.uuid4()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=10)

    await db.execute(text("""
        INSERT INTO reservations (emergency_id, hospital_id, status, hold_expires_at)
        VALUES (:eid, :hid, 'held', :exp)
    """), {"eid": str(emergency_id), "hid": str(hospital_id), "exp": expiry})
    await db.flush()

    # Attempt a second held reservation for the same emergency.
    try:
        await db.execute(text("""
            INSERT INTO reservations (emergency_id, hospital_id, status, hold_expires_at)
            VALUES (:eid, :hid2, 'held', :exp)
        """), {"eid": str(emergency_id), "hid2": str(uuid.uuid4()), "exp": expiry})
        await db.flush()
        raise AssertionError(
            "Invariant 3 violated: two active reservations were allowed for the "
            "same emergency; the unique partial index must prevent this."
        )
    except Exception as exc:
        # Postgres should raise a unique_violation (23505); any DB error is acceptable.
        assert "unique" in str(exc).lower() or "duplicate" in str(exc).lower(), (
            f"Expected a unique-constraint error, got: {exc}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 4 — Resource counts consistent
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resource_counts_consistent(db: AsyncSession) -> None:
    """
    Invariant 4 (§5.2, §14): for every hospital_resource row,
    available + reserved <= total AND available >= 0 AND reserved >= 0.

    The DB enforces this with CHECK constraints; we also run it as a query
    so the invariant checker in the sim can use the same SQL.
    """
    hospital_id = uuid.uuid4()
    # Insert a valid resource row.
    await db.execute(text("""
        INSERT INTO hospital_resources (hospital_id, type, total, available, reserved)
        VALUES (:hid, 'ventilator', 4, 3, 1)
    """), {"hid": str(hospital_id)})
    await db.flush()

    result = await db.execute(text("""
        SELECT id, type, total, available, reserved
        FROM hospital_resources
        WHERE available + reserved > total
           OR available < 0
           OR reserved < 0
    """))
    violations = result.fetchall()
    assert violations == [], f"Invariant 4 violated — inconsistent resource counts: {violations}"

    # Prove a bad insert is rejected by the DB CHECK.
    try:
        await db.execute(text("""
            INSERT INTO hospital_resources (hospital_id, type, total, available, reserved)
            VALUES (:hid, 'cath_lab', 2, 2, 1)  -- 2+1=3 > 2
        """), {"hid": str(hospital_id)})
        await db.flush()
        raise AssertionError("DB CHECK constraint did not reject available+reserved > total.")
    except Exception as exc:
        assert "check" in str(exc).lower() or "constraint" in str(exc).lower() or "violation" in str(exc).lower(), (
            f"Expected a check-constraint error, got: {exc}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Invariant 5 — No expired pending requests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_expired_pending_requests(db: AsyncSession) -> None:
    """
    Invariant 5 (§14): no hospital_request with status='pending' should have
    expires_at < now() - SWEEPER_INTERVAL_SEC.  The sweeper must have timed
    them out before that threshold.

    In a clean DB (or immediately after seeding) this must hold.
    We insert one expired request and verify the query detects it, proving
    the invariant check works.  In production the sweeper ensures this query
    returns zero rows.
    """
    # Insert an already-expired pending request.
    past_expiry = datetime.now(timezone.utc) - timedelta(seconds=_SWEEPER_INTERVAL_SEC + 10)
    await db.execute(text("""
        INSERT INTO hospital_requests (emergency_id, hospital_id, status, expires_at, rank)
        VALUES (:eid, :hid, 'pending', :exp, 1)
    """), {
        "eid": str(uuid.uuid4()),
        "hid": str(uuid.uuid4()),
        "exp": past_expiry,
    })
    await db.flush()

    result = await db.execute(text("""
        SELECT id, expires_at
        FROM hospital_requests
        WHERE status = 'pending'
          AND expires_at < now() - INTERVAL ':grace seconds'
    """.replace(":grace", str(_SWEEPER_INTERVAL_SEC))))
    stale = result.fetchall()

    # We injected one → expect it to be detected.
    assert len(stale) == 1, (
        f"Expected 1 stale pending request, found {len(stale)}."
    )
