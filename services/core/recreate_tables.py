import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.models.base import Base
# Import all models to register them
import app.db.models.control
import app.db.models.emergencies
import app.db.models.ambulances
import app.db.models.hospitals
import app.db.models.dispatch

async def recreate():
    engine = create_async_engine('postgresql+asyncpg://gh:gh@postgres:5432/goldenhour')
    async with engine.begin() as conn:
        # Drop only escalations table and recreate it
        await conn.run_sync(app.db.models.control.Escalation.__table__.drop, checkfirst=True)
        await conn.run_sync(app.db.models.control.Escalation.__table__.create, checkfirst=True)
    print("Recreated escalations table.")

if __name__ == '__main__':
    asyncio.run(recreate())
