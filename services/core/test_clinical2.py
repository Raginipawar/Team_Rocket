import asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from uuid import uuid4
from app.security.jwt import create_access_token

async def test_endpoints():
    engine = create_async_engine('postgresql+asyncpg://gh:gh@postgres:5432/goldenhour')
    Session = sessionmaker(engine, class_=AsyncSession)
    
    eid = uuid4()
    iid = uuid4()
    async with Session() as session:
        await session.execute(text(f"INSERT INTO incidents (id, location, status, priority, version) VALUES ('{iid}', 'SRID=4326;POINT(0 0)', 'NEW', 'ROUTINE', 1)"))
        await session.execute(text(f"INSERT INTO emergencies (id, incident_id, type, status, version) VALUES ('{eid}', '{iid}', 'medical', 'at_scene', 1)"))
        await session.commit()
    
    token = create_access_token(sub=str(uuid4()), role='paramedic')
    
    async with httpx.AsyncClient(base_url='http://localhost:8000') as client:
        r = await client.post(f'/api/v1/emergencies/{eid}/refused-transport', json={'note': 'refused'}, headers={'Authorization': f'Bearer {token}'})
        print('Refused transport response:', r.status_code, r.text)

if __name__ == '__main__':
    asyncio.run(test_endpoints())


