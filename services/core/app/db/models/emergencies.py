from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, JSON, ForeignKey, Float
from geoalchemy2 import Geography
from services.core.app.db.models.base import Base, TimestampMixin, VersionMixin

class Incident(TimestampMixin, VersionMixin, Base):
    __tablename__ = "incidents"
    
    caller_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, default="NEW", index=True)
    location: Mapped[str] = mapped_column(Geography(geometry_type='POINT', srid=4326))
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    priority: Mapped[str] = mapped_column(String, default="ROUTINE")

class Emergency(TimestampMixin, VersionMixin, Base):
    __tablename__ = "emergencies"
    
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")

class Patient(TimestampMixin, Base):
    __tablename__ = "patients"
    
    emergency_id: Mapped[str] = mapped_column(ForeignKey("emergencies.id"), index=True)
    triage_level: Mapped[str] = mapped_column(String)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

class FollowupAnswer(TimestampMixin, Base):
    __tablename__ = "followup_answers"
    
    emergency_id: Mapped[str] = mapped_column(ForeignKey("emergencies.id"))
    question: Mapped[str] = mapped_column(String)
    answer: Mapped[str] = mapped_column(String)

class TriageConfirmation(TimestampMixin, Base):
    __tablename__ = "triage_confirmations"
    
    emergency_id: Mapped[str] = mapped_column(ForeignKey("emergencies.id"))
    confirmed_level: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
