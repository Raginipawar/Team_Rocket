import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.db.models.base import Base, TimestampMixin

class User(TimestampMixin, Base):
    __tablename__ = "users"
    
    phone_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class HealthProfile(TimestampMixin, Base):
    __tablename__ = "health_profiles"
    
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    blood_group: Mapped[str | None] = mapped_column(String, nullable=True)
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list)
    medical_conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    medications: Mapped[list[str]] = mapped_column(JSON, default=list)

class EmergencyContact(TimestampMixin, Base):
    __tablename__ = "emergency_contacts"
    
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String)
    phone_number: Mapped[str] = mapped_column(String)
    relation: Mapped[str | None] = mapped_column(String, nullable=True)

class OtpCode(TimestampMixin, Base):
    __tablename__ = "otp_codes"
    
    phone_number: Mapped[str] = mapped_column(String, index=True)
    code: Mapped[str] = mapped_column(String)
    expires_at: Mapped[str] = mapped_column(String)
