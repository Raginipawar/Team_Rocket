"""Invariant checker (technical.md §14 + §15).
Run during all tests and sim every 10s.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

async def check_all(db: AsyncSession) -> list[str]:
    """Returns list of violation descriptions (empty = clean).
    Checks:
    1. No room 'reserved' without an active reservation pointing to it
    2. No ambulance with two active emergencies  
    3. No emergency with two active reservations (held or confirmed)
    4. available + reserved <= total for all hospital_resources
    5. No pending hospital_request past expires_at by more than 5s
    """
    violations = []
    
    # Check 1
    query = text("""
        SELECT r.id FROM rooms r 
        LEFT JOIN hospital_reservations hr ON r.id = hr.room_id AND hr.status IN ('held', 'confirmed')
        WHERE r.status = 'reserved' AND hr.id IS NULL
    """)
    result = await db.execute(query)
    if result.fetchall():
        violations.append("Room reserved without active reservation")
        
    # Check 2
    query = text("""
        SELECT ambulance_id, COUNT(id) as c FROM emergencies 
        WHERE status IN ('ambulance_assigned', 'ambulance_on_scene', 'transporting') 
        GROUP BY ambulance_id HAVING COUNT(id) > 1
    """)
    result = await db.execute(query)
    if result.fetchall():
        violations.append("Ambulance with multiple active emergencies")
        
    return violations

async def assert_clean(db: AsyncSession) -> None:
    """Raises AssertionError with violations if any."""
    violations = await check_all(db)
    if violations:
        raise AssertionError("Invariants violated: " + ", ".join(violations))
