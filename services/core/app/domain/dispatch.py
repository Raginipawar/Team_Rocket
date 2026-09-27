"""A provides to B (work-distribution.md §4.1). Real body: technical.md §11.1 --
starts the dispatch round loop (candidate query, B's eta/matrix + A's
dispatch-rank, offers, accept transaction). Needs emergencies/ambulances
tables (B's migrations) -- stub logs and returns so B's `start_selection` etc.
can be wired against a real call shape today."""

import logging
from uuid import UUID

logger = logging.getLogger("dispatch")


async def start_dispatch(session, *, emergency_id: UUID, priority: bool = False, reason: str) -> None:
    logger.info("start_dispatch (stub) emergency_id=%s priority=%s reason=%s", emergency_id, priority, reason)


async def redispatch_to_point(session, *, emergency_id: UUID, lat: float, lng: float, reason: str) -> None:
    logger.info("redispatch_to_point (stub) emergency_id=%s lat=%s lng=%s reason=%s",
                emergency_id, lat, lng, reason)
