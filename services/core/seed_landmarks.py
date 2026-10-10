import asyncio
import pandas as pd
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.models import Landmark

async def seed_landmarks():
    engine = create_async_engine('postgresql+asyncpg://gh:gh@postgres:5432/goldenhour')
    Session = sessionmaker(engine, class_=AsyncSession)
    
    df = pd.read_csv('/app/landmarks.csv')
    async with Session() as session:
        for idx, row in df.iterrows():
            loc = f'SRID=4326;POINT({row["lng"]} {row["lat"]})'
            landmark = Landmark(
                name=row['name'],
                type=row['kind'] if not pd.isna(row['kind']) else 'unknown',
                location=loc
            )
            session.add(landmark)
        await session.commit()
    print(f'Inserted {len(df)} landmarks.')

if __name__ == '__main__':
    asyncio.run(seed_landmarks())

