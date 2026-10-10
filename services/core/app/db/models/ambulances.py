import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, Float, String, ARRAY, JSON, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.db.models.base import Base, TimestampMixin, VersionMixin

class Ambulance(TimestampMixin, VersionMixin, Base):
    """technical.md Section5.2 -- ambulances table. Was mapped to columns
    (identifier, capabilities as JSON, status default "AVAILABLE") that
    don't exist on the real table at all -- the real columns are
    registration_no/equipment(text[])/status default 'offline' (lowercase,
    matching the real CHECK constraint; 'AVAILABLE' would have violated it
    outright). Found by actually running a real query against this model
    (domain/ops.py's get_overview) and getting UndefinedColumnError."""
    __tablename__ = "ambulances"

    registration_no: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    type: Mapped[str] = mapped_column(String)
    equipment: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(String, default="offline", index=True)
    current_location: Mapped[str | None] = mapped_column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    heading: Mapped[float | None] = mapped_column(Float)
    speed_kmh: Mapped[float | None] = mapped_column(Float)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_emergency_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    kyc_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    driver_license_no: Mapped[str | None] = mapped_column(Text)
    kyc_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)

class AmbulanceStatusLog(TimestampMixin, Base):
    __tablename__ = "ambulance_status_log"  # singular -- matches the already-applied live schema (0001_init.sql)
    
    ambulance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ambulances.id"), index=True)
    status: Mapped[str] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    context: Mapped[dict] = mapped_column(JSON, default=dict)
