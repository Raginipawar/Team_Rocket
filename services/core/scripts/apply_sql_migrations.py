"""Applies the raw .sql files in app/db/migrations/ that alembic doesn't
know about (only 0001 has a real alembic revision -- 0002 onward were
written as plain .sql and applied by hand to the dev DB, never through
alembic). Needed for a fresh database (Render) to end up with the same
schema the code actually expects. Tracks what's applied in its own
schema_migrations table so it's safe to run on every deploy, not just the
first one.
"""
import asyncio
import os
import re
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "app" / "db" / "migrations"
# alembic's own versions/0001_initial.py (ORM-metadata-generated) is NOT
# used -- confirmed live that it's stale/incomplete against the hand-written
# 0001_init.sql (missing generated columns like offload_delay_sec that the
# real dev DB, and this code, actually depend on). 0001_init.sql is the one
# that matches reality, so the whole chain runs through this raw-sql runner,
# alembic is not invoked at all for schema creation.
FILENAME_RE = re.compile(r"^\d{4}_.*\.sql$")


async def main() -> None:
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = {r["filename"] for r in await conn.fetch("SELECT filename FROM schema_migrations")}
        files = sorted(p for p in MIGRATIONS_DIR.iterdir() if FILENAME_RE.match(p.name))
        for path in files:
            if path.name in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute("INSERT INTO schema_migrations (filename) VALUES ($1)", path.name)
            print(f"applied {path.name}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
