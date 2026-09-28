import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, JSON, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.db.models.base import Base, TimestampMixin, VersionMixin

class Ambulance(TimestampMixin, VersionMixin, Base):
    __tablename__ = "ambulances"
    
    identifier: Mapped[str] = mapped_column(String, unique=True, index=True)
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="AVAILABLE", index=True)
    current_location: Mapped[str | None] = mapped_column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)

class AmbulanceStatusLog(TimestampMixin, Base):
    __tablename__ = "ambulance_status_logs"
    
    ambulance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ambulances.id"), index=True)
    status: Mapped[str] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    context: Mapped[dict] = mapped_column(JSON, default=dict)
