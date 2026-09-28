import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, JSON, Integer, Index, text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.db.models.base import Base, TimestampMixin, VersionMixin

class DispatchOffer(TimestampMixin, VersionMixin, Base):
    __tablename__ = "dispatch_offers"
    __table_args__ = (
        Index("uix_dispatch_offer_active", "ambulance_id", postgresql_where=text("status IN ('PENDING', 'ACCEPTED')"), unique=True),
    )
    
    emergency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"))
    ambulance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ambulances.id"))
    status: Mapped[str] = mapped_column(String, default="PENDING")
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))

class HospitalRequest(TimestampMixin, VersionMixin, Base):
    __tablename__ = "hospital_requests"
    
    emergency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"))
    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"))
    status: Mapped[str] = mapped_column(String, default="PENDING")

class Reservation(TimestampMixin, VersionMixin, Base):
    __tablename__ = "reservations"
    
    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"))
    emergency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"))
    status: Mapped[str] = mapped_column(String, default="ACTIVE")

class ReservationItem(TimestampMixin, Base):
    __tablename__ = "reservation_items"
    
    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reservations.id"))
    resource_type: Mapped[str] = mapped_column(String)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

class Handoff(TimestampMixin, VersionMixin, Base):
    __tablename__ = "handoffs"
    
    emergency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"))
    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"))
    ambulance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ambulances.id"))
    status: Mapped[str] = mapped_column(String, default="IN_PROGRESS")
