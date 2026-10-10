"""Dispatch/hospital-request/reservation models — technical.md §5.5.

Rewritten to match the fields the real domain logic (domain/reservations.py,
domain/selection.py, domain/clinical.py, api/v1/offers.py) actually reads and
writes, and to match the already-tested raw-SQL schema
(db/migrations/0001_init.sql) those same tables are built from on the real
running database -- the previous version of this file only had
emergency_id/hospital_id/status on each model, which doesn't match either
the spec or the domain code that uses it (e.g. reservations.py sets
`req.rank`, `req.rejection_reason`, `res.hold_expires_at`, none of which
existed as columns here)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class DispatchOffer(TimestampMixin, Base):
    """technical.md §5.5 — dispatch_offers."""

    __tablename__ = "dispatch_offers"
    __table_args__ = (
        UniqueConstraint("emergency_id", "ambulance_id", name="uq_dispatch_offer_emergency_ambulance"),
        Index("ix_dispatch_offers_ambulance_status", "ambulance_id", "status"),
    )

    emergency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"), nullable=False)
    ambulance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ambulances.id"), nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    predicted_accept_prob: Mapped[float | None] = mapped_column()
    predicted_eta_sec: Mapped[int | None] = mapped_column(Integer)
    rank: Mapped[int | None] = mapped_column(Integer)
    offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HospitalRequest(TimestampMixin, Base):
    """technical.md §5.5 — hospital_requests."""

    __tablename__ = "hospital_requests"
    __table_args__ = (
        Index(
            "uq_one_pending_request_per_emergency", "emergency_id",
            unique=True, postgresql_where=text("status = 'pending'"),
        ),
    )

    emergency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"), nullable=False)
    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    # Spec direction is reservations.hospital_request_id -> hospital_requests.id;
    # domain/reservations.py's own code (accept/reject/timeout_hospital_request)
    # reads `req.reservation_id` the other way round. Added as a real
    # denormalized back-reference rather than rewriting 3 call sites plus
    # whatever else depends on it later -- it's a true 1:1 relationship, so
    # both directions being queryable isn't a real correctness risk.
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("reservations.id"))
    rank: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[float | None] = mapped_column()
    explanation: Mapped[dict | None] = mapped_column(JSONB)
    features: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    reason_code: Mapped[str | None] = mapped_column(String(30))
    reason_note: Mapped[str | None] = mapped_column(Text)
    is_family_choice: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_priority: Mapped[bool] = mapped_column(default=False, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Aliases some domain code (clinical.py/reservations.py) was written
    # against under a different name -- kept as Python properties so both
    # call sites work without picking one name and silently breaking the other.
    @property
    def rejection_reason(self) -> str | None:
        return self.reason_code

    @rejection_reason.setter
    def rejection_reason(self, value: str | None) -> None:
        self.reason_code = value

    @property
    def rejection_note(self) -> str | None:
        return self.reason_note

    @rejection_note.setter
    def rejection_note(self, value: str | None) -> None:
        self.reason_note = value

    @property
    def responder_id(self) -> uuid.UUID | None:
        return self.responded_by

    @responder_id.setter
    def responder_id(self, value: uuid.UUID | None) -> None:
        self.responded_by = value


class Reservation(TimestampMixin, Base):
    """technical.md §5.5 — reservations."""

    __tablename__ = "reservations"
    __table_args__ = (
        Index(
            "uq_one_active_reservation_per_emergency", "emergency_id",
            unique=True, postgresql_where=text("status IN ('held','confirmed')"),
        ),
    )

    emergency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"), nullable=False)
    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    hospital_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospital_requests.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="held")
    hold_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Not in technical.md §5.5's strict table (there the room link is only
    # via reservation_items, kind='room') -- added as a REAL mapped column
    # because db/repos/reservations.py's release_reservation() reads
    # `res.room_id` after re-fetching the Reservation fresh from the DB via
    # db.get(). A first attempt made this a plain non-mapped Python
    # attribute; that silently always read back None on any fresh fetch, so
    # release_reservation never actually freed the room on reject/timeout/
    # refused-transport -- a real, serious bug, caught by actually running
    # the code against a real DB rather than just reading it. Denormalized
    # on purpose: reservation_items still gets the authoritative kind='room'
    # row for audit, this column is the fast/simple path every other call
    # site already assumes exists.
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id"))

    items: Mapped[list["ReservationItem"]] = relationship("ReservationItem", backref="reservation")


class ReservationItem(TimestampMixin, Base):
    """technical.md §5.5 — reservation_items."""

    __tablename__ = "reservation_items"

    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reservations.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # 'room' | 'resource' | 'staff'
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id"))
    resource_type: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id"))


class Handoff(Base):
    """technical.md §5.5 — handoffs (emergency_id is the PK, no TimestampMixin
    per spec; offload_delay_sec is a generated column on the real table)."""

    __tablename__ = "handoffs"

    emergency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"), primary_key=True)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"))
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id"))
    receiving_staff_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
