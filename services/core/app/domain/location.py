"""Location resolution (technical.md §10.1 step 3, wd-person-a-intake-dispatch.md §5):

1. GPS if accuracy_m <= 100.
2. Else landmark text (from extraction) -> gazetteer match (pg_trgm similarity,
   proximity-weighted to coarse GPS or profile home).
3. Else profile's home_location.
4. Else: still weak -> the first follow-up question asks for a landmark.

The gazetteer lookup is an injected `GazetteerLookup` protocol so the
fallback chain, which is pure logic, is independently testable.
PgTrgmGazetteerLookup below is the real implementation, now that the
`landmarks` table is actually populated (services/ml/app/geo/
gazetteer_export.py + data/seed/load_landmarks.py) -- domain/intake.py used
to always pass a NullGazetteer() stand-in instead."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

GPS_ACCURACY_THRESHOLD_M = 100.0


@dataclass
class ResolvedLocation:
    lat: float
    lng: float
    source: str  # "gps" | "landmark_geocode" | "profile_home"
    accuracy_m: float | None = None
    landmark_text: str | None = None


class GazetteerLookup(Protocol):
    async def match(
        self, landmark_text: str, *, near: tuple[float, float] | None = None
    ) -> tuple[float, float] | None:
        """pg_trgm similarity search, proximity-weighted to `near` when given.
        Returns (lat, lng) of the best match, or None if nothing crosses the
        similarity threshold."""
        ...


def _normalize(name: str) -> str:
    """Same normalization as gazetteer_export.py's normalize_name, so a
    query string and the stored name_normalized are comparable by pg_trgm."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("utf-8")
    name = name.lower()
    name = re.sub(r"[^\w\s]", "", name)
    return " ".join(name.split())


class PgTrgmGazetteerLookup:
    """Real implementation: pg_trgm similarity against the real `landmarks`
    table, proximity-weighted to `near` (within MAX_DISTANCE_KM) when given."""

    SIMILARITY_THRESHOLD = 0.3
    MAX_DISTANCE_KM = 15.0

    def __init__(self, session: AsyncSession):
        self.session = session

    async def match(
        self, landmark_text: str, *, near: tuple[float, float] | None = None
    ) -> tuple[float, float] | None:
        query = _normalize(landmark_text)
        if not query:
            return None

        params = {"q": query, "threshold": self.SIMILARITY_THRESHOLD}
        proximity_clause = ""
        if near is not None:
            lat, lng = near
            proximity_clause = (
                "AND ST_DWithin(location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :max_dist_m) "
            )
            params.update({"lat": lat, "lng": lng, "max_dist_m": self.MAX_DISTANCE_KM * 1000})

        row = (await self.session.execute(text(
            "SELECT ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng, "
            "similarity(name_normalized, :q) AS sim "
            "FROM landmarks "
            "WHERE similarity(name_normalized, :q) > :threshold " + proximity_clause +
            "ORDER BY sim DESC LIMIT 1"
        ), params)).mappings().first()

        if row is None:
            return None
        return (row["lat"], row["lng"])


async def resolve_location(
    *,
    gps: tuple[float, float] | None,
    accuracy_m: float | None,
    landmark_text: str | None,
    profile_home: tuple[float, float] | None,
    gazetteer: GazetteerLookup,
) -> ResolvedLocation | None:
    if gps is not None and accuracy_m is not None and accuracy_m <= GPS_ACCURACY_THRESHOLD_M:
        return ResolvedLocation(lat=gps[0], lng=gps[1], source="gps", accuracy_m=accuracy_m)

    if landmark_text:
        near = gps or profile_home
        match = await gazetteer.match(landmark_text, near=near)
        if match is not None:
            return ResolvedLocation(lat=match[0], lng=match[1], source="landmark_geocode",
                                     landmark_text=landmark_text)

    if profile_home is not None:
        return ResolvedLocation(lat=profile_home[0], lng=profile_home[1], source="profile_home")

    # Still weak: caller (domain/intake.py) must queue the first follow-up
    # question as "reply with nearest landmark / area" instead of a location fix.
    return None
