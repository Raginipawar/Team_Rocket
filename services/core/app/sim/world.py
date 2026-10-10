"""Simulator world state (technical.md §15).
All sim entities have is_simulated=True.
Speed multiplier scales all timers.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

@dataclass
class SimWorld:
    speed_multiplier: float = 1.0
    is_running: bool = False
    start_time: Optional[datetime] = None
    
    async def reset(self, db: AsyncSession) -> None:
        """Reset all simulated entities to initial state via DB."""
        await db.execute(text("DELETE FROM reservations"))
        await db.execute(text("DELETE FROM hospital_requests"))
        await db.execute(text("DELETE FROM dispatch_offers"))
        await db.execute(text("DELETE FROM emergencies"))
        await db.execute(text("DELETE FROM incidents"))
        await db.execute(text("DELETE FROM escalations"))
        await db.commit()
    
    async def set_speed(self, multiplier: float) -> None:
        """Update speed multiplier (1x-10x)."""
        self.speed_multiplier = max(1.0, min(10.0, multiplier))
