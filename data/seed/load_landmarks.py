"""Loads services/ml's gazetteer_export.py output (data/processed/landmarks.csv)
into the real `landmarks` table (db/migrations/0001_init.sql) -- the table
existed with a pg_trgm index ready for exactly this, but nothing had ever
actually populated it, so core/app/domain/location.py's landmark-matching
fallback tier silently never matched anything for any caller.

Usage: python data/seed/load_landmarks.py [csv_path]
"""

import asyncio
import csv
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://gh:gh@localhost:5432/goldenhour")


async def main(csv_path: str) -> None:
    engine = create_async_engine(DATABASE_URL)
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("name") or not row.get("lat") or not row.get("lng"):
                continue
            alt_names = [n for n in (row.get("alt_names") or "").split("|") if n]
            rows.append({
                "name": row["name"], "name_normalized": row["name_normalized"],
                "alt_names": alt_names, "kind": row.get("kind") or "unknown",
                "lat": float(row["lat"]), "lng": float(row["lng"]),
            })

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE landmarks"))
        for r in rows:
            await conn.execute(text(
                "INSERT INTO landmarks (name, name_normalized, alt_names, kind, location) "
                "VALUES (:name, :name_normalized, :alt_names, :kind, "
                "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography)"
            ), r)

    await engine.dispose()
    print(f"loaded {len(rows)} landmarks from {csv_path} into the real landmarks table")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/landmarks.csv"
    asyncio.run(main(path))
