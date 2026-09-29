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
        # Reset emergencies, reservations, etc. for simulated entities
        await db.execute(text("DELETE FROM emergencies WHERE is_simulated = TRUE"))
        await db.execute(text("DELETE FROM hospital_reservations WHERE emergency_id IN (SELECT id FROM emergencies WHERE is_simulated = TRUE)"))
        await db.execute(text("DELETE FROM outbox_events"))
        await db.commit()
    
    async def set_speed(self, multiplier: float) -> None:
        """Update speed multiplier (1x-10x)."""
        self.speed_multiplier = max(1.0, min(10.0, multiplier))
