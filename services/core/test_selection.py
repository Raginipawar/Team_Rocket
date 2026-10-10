import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select
from uuid import uuid4
from app.domain.selection import start_selection
from app.db.models.control import Escalation

async def test_selection():
    engine = create_async_engine('postgresql+asyncpg://gh:gh@postgres:5432/goldenhour')
    Session = sessionmaker(engine, class_=AsyncSession)
    
    eid = uuid4()
    iid = uuid4()
    async with Session() as session:
        # Create an incident way out in the ocean (lat=0, lng=0) so no hospitals are within 25km
        await session.execute(text(f"INSERT INTO incidents (id, location, status, priority, version) VALUES ('{iid}', 'SRID=4326;POINT(0 0)', 'NEW', 'ROUTINE', 1)"))
        await session.execute(text(f"INSERT INTO emergencies (id, incident_id, type, status, version) VALUES ('{eid}', '{iid}', 'medical', 'hospital_selecting', 1)"))
        await session.commit()
    
        # Run selection
        try:
            await start_selection(session, None, 'http://ml:8001', eid, 'triage_confirm')
            await session.commit()
            
            # Check for escalation
            res = await session.execute(select(Escalation).where(Escalation.emergency_id == eid))
            esc = res.scalar_one_or_none()
            if esc and esc.escalation_type == 'no_hospital':
                print('Success: no_hospital escalation created!')
            else:
                print('Fail: escalation not found', esc)
        except Exception as e:
            print('Error during selection:', e)

if __name__ == '__main__':
    asyncio.run(test_selection())
