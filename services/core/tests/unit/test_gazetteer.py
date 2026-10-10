"""Landmark gazetteer (technical.md Section10.1 step 3): the `landmarks`
table and its pg_trgm index existed, but nothing ever populated it and no
real GazetteerLookup implementation existed -- domain/intake.py always
passed a NullGazetteer() stand-in that unconditionally returned None. Now
real: services/ml/app/geo/gazetteer_export.py (fixed an osmnx 2.x API
mismatch that would have crashed on its first real run) + data/seed/
load_landmarks.py populate the table from real OSM data; this test exercises
the real PgTrgmGazetteerLookup against it."""

import pytest
from sqlalchemy import text

from app.db.session import get_session
from app.domain.location import PgTrgmGazetteerLookup

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_exact_name_match():
    async with get_session() as session:
        count = (await session.execute(text("SELECT count(*) FROM landmarks"))).scalar_one()
        if count == 0:
            pytest.skip("landmarks table is empty -- run data/seed/load_landmarks.py first")

        gazetteer = PgTrgmGazetteerLookup(session)
        row = (await session.execute(text("SELECT name, ST_Y(location::geometry) AS lat, "
                                            "ST_X(location::geometry) AS lng FROM landmarks LIMIT 1"))).mappings().first()
        result = await gazetteer.match(row["name"])
        assert result is not None
        assert abs(result[0] - row["lat"]) < 0.001
        assert abs(result[1] - row["lng"]) < 0.001


async def test_typo_tolerant_match():
    async with get_session() as session:
        exists = (await session.execute(text(
            "SELECT 1 FROM landmarks WHERE name_normalized = 'swargate' LIMIT 1"
        ))).scalar_one_or_none()
        if exists is None:
            pytest.skip("'Swargate' not present in this run's landmark data")

        gazetteer = PgTrgmGazetteerLookup(session)
        exact = await gazetteer.match("Swargate")
        typo = await gazetteer.match("swargat")
        assert exact is not None and typo is not None
        assert exact == typo


async def test_nonsense_query_returns_none():
    async with get_session() as session:
        gazetteer = PgTrgmGazetteerLookup(session)
        result = await gazetteer.match("zzxxqqww_not_a_real_place_12345")
        assert result is None


async def test_proximity_filter_excludes_far_matches():
    async with get_session() as session:
        gazetteer = PgTrgmGazetteerLookup(session)
        # Pune landmark name queried with a "near" point far outside Pune (Mumbai) --
        # the proximity filter should exclude it even if the name similarity is high.
        far_away = (19.0760, 72.8777)
        result = await gazetteer.match("Swargate", near=far_away)
        assert result is None
