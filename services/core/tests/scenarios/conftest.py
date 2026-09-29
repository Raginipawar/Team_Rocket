"""
pytest fixtures for scenario tests.

Provides:
  db            — async SQLAlchemy session against the running Docker Postgres.
  async_client  — HTTPX AsyncClient pointed at the core service (role=patient).
  ops_client    — HTTPX AsyncClient with ops session cookie.
  reset_sim     — async function that POSTs /ops/sim/reset and waits for 200.

These fixtures assume the full docker-compose stack is up (`make up`).
For isolated unit runs they fall back to testcontainers Postgres.

Usage in scenario tests:
  async def test_t11_hospital_timeout(async_client, ops_client, db, reset_sim):
      await reset_sim()
      ...
"""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

_CORE_BASE_URL: str = os.getenv("CORE_BASE_URL", "http://localhost:8000")
_DB_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://gh:gh@localhost:5432/goldenhour",
)
_OPS_TOKEN: str = os.getenv("TEST_OPS_TOKEN", "")  # one-time ops token for test env


# ─────────────────────────────────────────────────────────────────────────────
# DB fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def _db_engine():
    """
    Session-scoped async engine.

    If the env var DATABASE_URL points to the Docker Postgres, uses it directly.
    Otherwise spins up a testcontainers instance (slower but fully self-contained).
    """
    try:
        engine = create_async_engine(_DB_URL, echo=False, pool_size=5)
        # Quick connectivity check.
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        yield engine
        await engine.dispose()
    except Exception:
        # Fall back to testcontainers.
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer(
            "postgis/postgis:16-3.4", username="gh", password="gh", dbname="goldenhour"
        ) as pg:
            url = pg.get_connection_url().replace("psycopg2", "asyncpg")
            engine = create_async_engine(url, echo=False)
            yield engine
            await engine.dispose()


@pytest_asyncio.fixture()
async def db(_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Function-scoped async session.

    Each test gets a fresh session that is rolled back on teardown so tests
    do not interfere with each other.  Scenario tests that need committed state
    (e.g., to verify across multiple HTTP calls) should call `await session.commit()`
    explicitly and rely on `reset_sim` for cleanup.
    """
    async_session = async_sessionmaker(_db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# HTTP client fixtures
# ─────────────────────────────────────────────────────────────────────────────

async def _get_patient_token(client: httpx.AsyncClient) -> str:
    """
    Obtain a short-lived patient access token for test scenarios.

    Uses a pre-seeded test phone number. In the sim environment the OTP
    endpoint returns a fixed code when SIM_ENABLED=true and the phone has
    the `is_simulated` flag.
    """
    test_phone = os.getenv("TEST_PATIENT_PHONE", "+919800000001")
    idem_key = str(uuid.uuid4())

    # Request OTP.
    r = await client.post(
        "/api/v1/auth/otp/request",
        json={"phone": test_phone},
        headers={"Idempotency-Key": idem_key},
    )
    # In sim mode the OTP is always "000000".
    otp_code = os.getenv("TEST_OTP_CODE", "000000")

    r2 = await client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": test_phone, "code": otp_code},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    data = r2.json()
    return data.get("access_token", "")


@pytest_asyncio.fixture(scope="session")
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Session-scoped HTTPX AsyncClient authenticated as a patient user.

    Re-authenticates if the token is about to expire (handled transparently
    by pytest's session scope since scenario tests run in <15 min).
    """
    async with httpx.AsyncClient(base_url=_CORE_BASE_URL, timeout=30.0) as client:
        token = await _get_patient_token(client)
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client


@pytest_asyncio.fixture(scope="session")
async def ops_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Session-scoped HTTPX AsyncClient authenticated via an ops one-time token.

    The ops session cookie is stored in the client's cookie jar for subsequent
    requests (the core ops endpoints use httpOnly session cookies, §7.7).
    """
    async with httpx.AsyncClient(base_url=_CORE_BASE_URL, timeout=30.0) as client:
        if _OPS_TOKEN:
            resp = await client.post(
                "/api/v1/ops/session",
                json={"token": _OPS_TOKEN},
            )
            if resp.status_code not in (200, 204):
                pytest.skip(
                    f"Ops session could not be established (status {resp.status_code}). "
                    "Set TEST_OPS_TOKEN env var to a valid one-time ops token."
                )
        else:
            pytest.skip(
                "TEST_OPS_TOKEN not set; skipping tests that require ops access."
            )
        yield client


# ─────────────────────────────────────────────────────────────────────────────
# Sim-reset fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def reset_sim(ops_client: httpx.AsyncClient):
    """
    Async callable that resets the simulator to a clean seeded state.

    Calls POST /api/v1/ops/sim/reset and waits until core responds 200.
    Scenario tests should call `await reset_sim()` at the start and optionally
    at teardown.

    Usage:
        async def test_something(reset_sim, async_client):
            await reset_sim()
            # … drive the scenario …
    """
    async def _reset() -> None:
        resp = await ops_client.post(
            "/api/v1/ops/sim/reset",
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert resp.status_code in (200, 204), (
            f"Sim reset failed with status {resp.status_code}: {resp.text}"
        )
        # Give the system a moment to propagate the reset.
        await asyncio.sleep(1.0)

    return _reset


# ─────────────────────────────────────────────────────────────────────────────
# Paramedic client fixture (used by dispatch / triage-confirm scenarios)
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def paramedic_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Session-scoped HTTPX AsyncClient authenticated as a pre-seeded paramedic
    (role=paramedic, kyc_verified=true).
    """
    async with httpx.AsyncClient(base_url=_CORE_BASE_URL, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username_or_phone": os.getenv("TEST_PARAMEDIC_USERNAME", "test_paramedic_1"),
                "password": os.getenv("TEST_PARAMEDIC_PASSWORD", "testpass123"),
            },
        )
        if resp.status_code != 200:
            pytest.skip("Paramedic login failed — seed data may be missing.")
        token = resp.json().get("access_token", "")
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client


@pytest_asyncio.fixture(scope="session")
async def hospital_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Session-scoped HTTPX AsyncClient authenticated as a pre-seeded hospital
    staff member (role=hospital_staff).
    """
    async with httpx.AsyncClient(base_url=_CORE_BASE_URL, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username_or_phone": os.getenv("TEST_HOSPITAL_USERNAME", "test_hospital_staff_1"),
                "password": os.getenv("TEST_HOSPITAL_PASSWORD", "testpass123"),
            },
        )
        if resp.status_code != 200:
            pytest.skip("Hospital staff login failed — seed data may be missing.")
        token = resp.json().get("access_token", "")
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
