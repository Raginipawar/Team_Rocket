from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import text, DateTime, Integer
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), onupdate=datetime.utcnow)

class VersionMixin:
    version: Mapped[int] = mapped_column(Integer, default=1)
