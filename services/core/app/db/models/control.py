from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, JSON, Integer, Float, ForeignKey, DateTime, Boolean
from geoalchemy2 import Geography
from services.core.app.db.models.base import Base, TimestampMixin

class Escalation(TimestampMixin, Base):
    __tablename__ = "escalations"
    
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="PENDING")

class OneTimeToken(TimestampMixin, Base):
    __tablename__ = "one_time_tokens"
    
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)

class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="UNREAD")

class SmsMessage(TimestampMixin, Base):
    __tablename__ = "sms_messages"
    
    phone_number: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="PENDING")

class CallerReputation(TimestampMixin, Base):
    __tablename__ = "caller_reputations"
    
    phone_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    score: Mapped[int] = mapped_column(Integer, default=100)

class IdempotencyKey(TimestampMixin, Base):
    __tablename__ = "idempotency_keys"
    
    key: Mapped[str] = mapped_column(String, unique=True, index=True)
    response_body: Mapped[dict] = mapped_column(JSON)
    status_code: Mapped[int] = mapped_column(Integer)

class PushSubscription(TimestampMixin, Base):
    __tablename__ = "push_subscriptions"
    
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token: Mapped[str] = mapped_column(String)

class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_log"
    
    table_name: Mapped[str] = mapped_column(String)
    record_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    changes: Mapped[dict] = mapped_column(JSON)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)

class Landmark(TimestampMixin, Base):
    __tablename__ = "landmarks"
    
    name: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(Geography(geometry_type='POINT', srid=4326))

class DemandForecast(TimestampMixin, Base):
    __tablename__ = "demand_forecasts"
    
    region: Mapped[str] = mapped_column(Geography(geometry_type='POLYGON', srid=4326))
    forecasted_demand: Mapped[float] = mapped_column(Float)
    time_window: Mapped[DateTime] = mapped_column(DateTime(timezone=True))

class MlPrediction(TimestampMixin, Base):
    __tablename__ = "ml_predictions"
    
    model_name: Mapped[str] = mapped_column(String)
    input_data: Mapped[dict] = mapped_column(JSON)
    prediction: Mapped[dict] = mapped_column(JSON)
