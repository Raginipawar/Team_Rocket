import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, JSON, Integer, Float, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.db.models.base import Base, TimestampMixin


class Escalation(TimestampMixin, Base):
    __tablename__ = "escalations"

    escalation_type: Mapped[str] = mapped_column(String, nullable=False)
    emergency_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    options: Mapped[list] = mapped_column(JSON, default=list)
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_option_id: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    default_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_message_ids: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=0)


class OneTimeToken(TimestampMixin, Base):
    __tablename__ = "one_time_tokens"

    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    purpose: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="unread")


class SmsMessage(TimestampMixin, Base):
    __tablename__ = "sms_messages"

    phone_number: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    emergency_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id", ondelete="SET NULL"), nullable=True)


class CallerReputation(TimestampMixin, Base):
    __tablename__ = "caller_reputations"

    phone_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    score: Mapped[int] = mapped_column(Integer, default=100)
    prank_count: Mapped[int] = mapped_column(Integer, default=0)


class IdempotencyKey(TimestampMixin, Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String, unique=True, index=True)
    response_body: Mapped[dict] = mapped_column(JSON)
    status_code: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PushSubscription(TimestampMixin, Base):
    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    token: Mapped[str] = mapped_column(String)
    platform: Mapped[str | None] = mapped_column(String, nullable=True)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_log"

    table_name: Mapped[str] = mapped_column(String)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    changes: Mapped[dict] = mapped_column(JSON, default=dict)


class Landmark(TimestampMixin, Base):
    __tablename__ = "landmarks"

    name: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(Geography(geometry_type='POINT', srid=4326))


class DemandForecast(TimestampMixin, Base):
    __tablename__ = "demand_forecasts"

    h3_index: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    predicted_demand: Mapped[float] = mapped_column(Float)


class MlPrediction(TimestampMixin, Base):
    __tablename__ = "ml_predictions"

    model_name: Mapped[str] = mapped_column(String)
    model_version: Mapped[str] = mapped_column(String)
    inputs: Mapped[dict] = mapped_column(JSON)
    outputs: Mapped[dict] = mapped_column(JSON)
