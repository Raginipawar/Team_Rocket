"""
Root conftest.py for the core test suite.

PROBLEM: When pytest runs inside the `core` Docker container, testcontainers
spins up a new Postgres on the *host* Docker bridge (172.17.0.1) and tells
Python "connect to 172.17.0.1:<random-port>".  The core container is on the
isolated `infra_default` network and cannot route to that IP, causing:
  ConnectionRefusedError: [Errno 111] Connect call failed ('172.17.0.1', ...)

SOLUTION: Put the testcontainers Postgres on the SAME Docker network as this
container (`infra_default`), then connect using the container's **internal**
hostname/IP on port 5432 — never via the host-mapped port.

How it works:
  1. We detect whether we're running inside Docker by checking `/.dockerenv`.
  2. If inside Docker, we use the `DOCKER_NETWORK` env var (default: `infra_default`)
     and override the testcontainers connection URL to use the container's internal
     IP (from `docker inspect`) on port 5432.
  3. If running on the host directly, we fall back to the normal host-mapped URL.

The helper `network_aware_postgres_url()` is imported by individual test modules.
"""
from __future__ import annotations

import os
import json
import socket
import subprocess
from contextlib import contextmanager
from typing import Generator

# The Docker network that the `core` container belongs to.
# Matches the compose project name (infra) + network name (default).
DOCKER_NETWORK: str = os.getenv("DOCKER_NETWORK", "infra_default")

# Are we running inside a Docker container?
_INSIDE_DOCKER: bool = os.path.exists("/.dockerenv")

# ── Testcontainers bootstrap (must happen before any testcontainers import) ──
# When running inside Docker, Ryuk's host-mapped port is unreachable from the
# container's isolated network.  Disable it — cleanup is done by context managers.
if _INSIDE_DOCKER:
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
    os.environ.setdefault("DOCKER_HOST", "unix:///var/run/docker.sock")
    os.environ.setdefault("DOCKER_NETWORK", DOCKER_NETWORK)


def _container_internal_ip(container_id: str, network: str) -> str:
    """Return the internal IP of a container, trying the named network first.

    Uses the Docker Python SDK (available since docker is a test dependency).
    Falls back to the container's first available IP if the named network
    isn't present (e.g. if with_kwargs(network=) silently didn't work).
    """
    import docker as docker_sdk  # type: ignore[import]
    client = docker_sdk.from_env()
    try:
        container = client.containers.get(container_id)
        container.reload()
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        if network in networks and networks[network].get("IPAddress"):
            return networks[network]["IPAddress"]
        # Fallback: first non-empty IP across all networks
        for net_info in networks.values():
            ip = net_info.get("IPAddress", "")
            if ip:
                return ip
        # Last resort: try get_container_host_ip from testcontainers
        raise RuntimeError(f"No IP found for container {container_id}")
    finally:
        client.close()


@contextmanager
def network_aware_postgres(
    image: str = "postgis/postgis:16-3.4",
    username: str = "gh",
    password: str = "gh",
    dbname: str = "gh_test",
) -> Generator[str, None, None]:
    """
    Context manager that yields an asyncpg connection URL for a temporary
    PostGIS container.

    When running INSIDE Docker:
        - Attaches the new container to `DOCKER_NETWORK` so the core container
          can reach it.
        - Connects via the container's internal IP on port 5432.

    When running on the HOST:
        - Uses the standard testcontainers host-mapped port (normal behaviour).

    Usage::

        with network_aware_postgres(dbname="my_test_db") as url:
            engine = create_async_engine(url)
            ...
    """
    from testcontainers.postgres import PostgresContainer

    if not _INSIDE_DOCKER:
        # ── Host mode: standard testcontainers behaviour ──────────────────────
        with PostgresContainer(
            image, username=username, password=password, dbname=dbname
        ) as pg:
            url = pg.get_connection_url().replace("psycopg2", "asyncpg")
            yield url
        return

    # ── Docker-in-Docker mode: post-start network attach ─────────────────────
    # Strategy:
    #   1. Start the container normally (it comes up on the default bridge).
    #   2. Attach it to DOCKER_NETWORK via the Docker SDK — guaranteed to work.
    #   3. Connect using the container's internal IP on that network (port 5432).
    #
    # This avoids all testcontainers networking abstractions and is robust
    # across testcontainers versions.
    import docker as docker_sdk  # type: ignore[import]

    pg = PostgresContainer(
        image, username=username, password=password, dbname=dbname
    )

    with pg:
        container_id = pg.get_container_id()

        # Attach the running container to our shared network.
        client = docker_sdk.from_env()
        try:
            net = client.networks.get(DOCKER_NETWORK)
            net.connect(container_id)
        except docker_sdk.errors.APIError as e:
            if "already exists" not in str(e).lower():
                raise
        finally:
            client.close()

        # Resolve the internal IP on the shared network.
        internal_ip = _container_internal_ip(container_id, DOCKER_NETWORK)
        url = (
            f"postgresql+asyncpg://{username}:{password}"
            f"@{internal_ip}:5432/{dbname}"
        )
        yield url


async def execute_script(conn, sql: str) -> None:
    """Execute a multi-statement SQL script with asyncpg by splitting on semicolons."""
    from sqlalchemy import text
    for stmt in sql.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            await conn.execute(text(stmt))


