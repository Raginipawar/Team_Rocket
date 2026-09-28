from typing import Annotated
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.engine import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]

class Pagination:
    def __init__(self, skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100)):
        self.skip = skip
        self.limit = limit

try:
    from app.security.deps import require_role
except ImportError:
    def require_role(*roles):
        def dummy_dep():
            pass
        return dummy_dep
