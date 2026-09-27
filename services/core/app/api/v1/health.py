from fastapi import APIRouter, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.db.session import get_db
from sqlalchemy import text

router = APIRouter(tags=["health"])

@router.get("/healthz")
async def healthz():
    return {"status": "ok"}

@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        # Add checks for Redis, ML, and OSRM here
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail={"error": {"code": "SERVICE_UNAVAILABLE", "message": str(e)}})
