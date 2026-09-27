"""Location resolution (technical.md §10.1 step 3, wd-person-a-intake-dispatch.md §5):

1. GPS if accuracy_m <= 100.
2. Else landmark text (from extraction) -> gazetteer match (pg_trgm similarity,
   proximity-weighted to coarse GPS or profile home).
3. Else profile's home_location.
4. Else: still weak -> the first follow-up question asks for a landmark.

The gazetteer lookup itself needs the `landmarks` table (technical.md §5,
seeded by B from the OSM gazetteer) -- not available until B's DB models land.
This module takes it as an injected `GazetteerLookup` protocol so the fallback
chain, which is pure logic, can be written and tested today."""

from dataclasses import dataclass
from typing import Protocol

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
