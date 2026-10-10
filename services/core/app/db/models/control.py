import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, String, JSON, Integer, Float, ForeignKey, DateTime, Boolean, Text, text
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.db.models.base import Base, TimestampMixin


class Escalation(TimestampMixin, Base):
    """technical.md Section5.6 -- escalations table. Was mapped to columns
    (escalation_type, context, resolved_by, resolution_option_id) that don't
    exist on the real table at all, and was MISSING real columns
    (summary, incident_id, default_option_id, chosen_option_id, claimed_at)
    -- every one of db/repos/escalations.py's claim/resolve functions would
    have raised UndefinedColumnError on its first real call. domain/
    escalation.py's raise_escalation (raw SQL) already used the correct
    real column names -- only this ORM model and the repo built on it were
    wrong, found by actually calling ops.py's endpoints with a real request."""
    __tablename__ = "escalations"

    type: Mapped[str] = mapped_column(String, nullable=False)
    emergency_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id", ondelete="SET NULL"), nullable=True)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list] = mapped_column(JSON, default=list)
    default_option_id: Mapped[str | None] = mapped_column(String, nullable=True)
    chosen_option_id: Mapped[str | None] = mapped_column(String, nullable=True)
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    default_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_message_ids: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # domain/ops.py reads e.escalation_type -- alias so that call site
    # doesn't need to change along with the column name fix.
    @property
    def escalation_type(self) -> str:
        return self.type


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
    __tablename__ = "caller_reputation"  # singular -- matches the already-applied live schema (0001_init.sql)

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


class AuditLog(Base):
    """technical.md Section5.6 -- audit_log table. Was mapped to a shape
    that doesn't exist at all (table_name/record_id/changes columns, a UUID
    primary key via TimestampMixin, an updated_at column) -- the real table
    (append-only, DB-level rules forbid UPDATE/DELETE) has a bigserial id,
    a single `at` timestamp (no updated_at), entity/entity_id (not
    table_name/record_id), and separate before/after jsonb columns (not one
    merged `changes`). domain/audit.py's write() (raw SQL, already tested)
    already used the real columns -- only this read-side ORM model was
    wrong, which is what get_ops_audit queries through."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    actor_type: Mapped[str | None] = mapped_column(String)
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity: Mapped[str | None] = mapped_column(String)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


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
