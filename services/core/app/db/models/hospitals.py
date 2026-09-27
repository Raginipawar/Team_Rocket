"""Full hospital/room/resource/staff SQLAlchemy models — technical.md §5.2."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from .base import Base, TimestampMixin


class Hospital(TimestampMixin, Base):
    """technical.md §5.2 — hospitals table."""

    __tablename__ = "hospitals"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    location: Mapped[object] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    er_entrance_note: Mapped[str | None] = mapped_column(Text)
    duty_manager_phone: Mapped[str | None] = mapped_column(String(20))
    capabilities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    stabilization_capable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rooms: Mapped[list["Room"]] = relationship("Room", back_populates="hospital", lazy="select")
    resources: Mapped[list["HospitalResource"]] = relationship(
        "HospitalResource", back_populates="hospital", lazy="select"
    )
    staff: Mapped[list["Staff"]] = relationship("Staff", back_populates="hospital", lazy="select")


class Room(TimestampMixin, Base):
    """technical.md §5.2 — rooms table."""

    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("hospital_id", "code", name="uq_hospital_room_code"),
        Index("ix_rooms_hospital_type_status", "hospital_id", "type", "status"),
        CheckConstraint(
            "type IN ('er_bed','resus_bay','trauma_bay','icu_bed','labour_room','burns_unit','pediatric_er')",
            name="chk_room_type",
        ),
        CheckConstraint(
            "status IN ('free','reserved','occupied','cleaning','out_of_service')",
            name="chk_room_status",
        ),
    )

    hospital_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hospitals.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    location_note: Mapped[str | None] = mapped_column(Text)
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False, default=99)
    reservation_id: Mapped[str | None] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="rooms")


class HospitalResource(TimestampMixin, Base):
    """technical.md §5.2 — hospital_resources table."""

    __tablename__ = "hospital_resources"
    __table_args__ = (
        UniqueConstraint("hospital_id", "type", name="uq_hospital_resource_type"),
        CheckConstraint("available >= 0", name="chk_resource_available_gte_zero"),
        CheckConstraint("reserved >= 0", name="chk_resource_reserved_gte_zero"),
        CheckConstraint(
            "available + reserved <= total", name="chk_resource_available_plus_reserved_lte_total"
        ),
    )

    hospital_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hospitals.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="resources")


class Staff(TimestampMixin, Base):
    """technical.md §5.2 — staff table."""

    __tablename__ = "staff"

    hospital_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hospitals.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="staff")
    shifts: Mapped[list["StaffShift"]] = relationship("StaffShift", back_populates="staff_member")


class StaffShift(TimestampMixin, Base):
    """technical.md §5.2 — staff_shifts table.

    The exclusion constraint (no overlapping shifts per staff member) is added
    via raw SQL in the Alembic migration because SQLAlchemy doesn't natively
    support EXCLUDE USING gist with tstzrange:

        ALTER TABLE staff_shifts ADD CONSTRAINT no_shift_overlap
          EXCLUDE USING gist (staff_id WITH =, tstzrange(start_at, end_at) WITH &&);
    """

    __tablename__ = "staff_shifts"

    staff_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("staff.id"), nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    staff_member: Mapped["Staff"] = relationship("Staff", back_populates="shifts")


class HospitalOccupancyHistory(Base):
    """technical.md §5.2 — hospital_occupancy_history (composite PK, no updated_at trigger)."""

    __tablename__ = "hospital_occupancy_history"
    __table_args__ = (
        # PK is (hospital_id, room_type, ts) — declared below
    )

    hospital_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hospitals.id"), primary_key=True
    )
    room_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    free: Mapped[int] = mapped_column(Integer, nullable=False)
    occupied: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False)
