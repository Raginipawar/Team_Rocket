import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def alter_db():
    engine = create_async_engine('postgresql+asyncpg://gh:gh@postgres:5432/goldenhour')
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE escalations ADD COLUMN escalation_type VARCHAR NOT NULL DEFAULT 'unknown'"))
            print("Added escalation_type")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(alter_db())

