import asyncio
import httpx
from uuid import uuid4
from app.security.jwt import create_access_token

async def test_ops():
    token = create_access_token(sub=str(uuid4()), role='ops')
    
    async with httpx.AsyncClient(base_url='http://localhost:8000') as client:
        r1 = await client.get('/api/v1/ops/overview', headers={'Authorization': f'Bearer {token}'})
        print('Overview:', r1.status_code)
        
        r2 = await client.get('/api/v1/ops/audit', headers={'Authorization': f'Bearer {token}'})
        print('Audit:', r2.status_code)
        
        r3 = await client.get('/api/v1/ops/scenarios', headers={'Authorization': f'Bearer {token}'})
        print('Scenarios:', r3.status_code)

if __name__ == '__main__':
    asyncio.run(test_ops())
