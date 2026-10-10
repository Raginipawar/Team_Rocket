"""Emergency/incident/patient models — technical.md §5.4.

Rewritten to match the already-tested raw-SQL schema (db/migrations/0001_init.sql)
column-for-column. The previous version of this file had `Incident.caller_id`/
`priority`/`description` (none of which are in the spec) and `Emergency.type`/
`status` only -- missing acuity, facility, channel, raw_text, location, and
every other field technical.md §5.4 and B's OWN domain code (clinical.py does
`em.acuity = new_acuity`, `em.status`, reservations.py reads `em.hospital_id`)
actually reference. None of that domain code could ever have run successfully
against this model as it was."""

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class Incident(TimestampMixin, Base):
    """technical.md §5.4 — incidents (groups duplicate calls / MCI)."""

    __tablename__ = "incidents"

    location: Mapped[object | None] = mapped_column(Geography(geometry_type="POINT", srid=4326))
    patient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_mass_casualty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class Emergency(TimestampMixin, Base):
    """technical.md §5.4 — emergencies. version is plain Integer here (not
    VersionMixin) because the real column has no server_default, matching
    the explicit version=1 the intake pipeline sets on create."""

    __tablename__ = "emergencies"

    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("incidents.id"))
    caller_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    caller_phone: Mapped[str | None] = mapped_column(String(20))
    channel: Mapped[str] = mapped_column(String(20), nullable=False)

    raw_text: Mapped[str | None] = mapped_column(Text)
    audio_object_key: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    stt_confidence: Mapped[float | None] = mapped_column(Float)
    extracted: Mapped[dict | None] = mapped_column(JSONB)

    location: Mapped[object | None] = mapped_column(Geography(geometry_type="POINT", srid=4326))
    location_accuracy_m: Mapped[float | None] = mapped_column(Float)
    landmark_text: Mapped[str | None] = mapped_column(Text)
    location_source: Mapped[str | None] = mapped_column(String(20))

    ai_acuity: Mapped[str | None] = mapped_column(String(20))
    ai_facility: Mapped[str | None] = mapped_column(String(20))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_probs: Mapped[dict | None] = mapped_column(JSONB)
    needs_review: Mapped[bool | None] = mapped_column(Boolean)

    final_acuity: Mapped[str | None] = mapped_column(String(20))
    final_facility: Mapped[str | None] = mapped_column(String(20))

    required_ambulance_type: Mapped[str | None] = mapped_column(String(10))
    fragility: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mlc_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prank_score: Mapped[float | None] = mapped_column(Float)
    prank_verified: Mapped[bool | None] = mapped_column(Boolean)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    predicted_resources: Mapped[dict | None] = mapped_column(JSONB)
    handover_note: Mapped[dict | None] = mapped_column(JSONB)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="received")
    ambulance_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ambulances.id"))
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"))
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    eta_to_patient_sec: Mapped[int | None] = mapped_column(Integer)
    eta_to_hospital_sec: Mapped[int | None] = mapped_column(Integer)
    eta_low_sec: Mapped[int | None] = mapped_column(Integer)
    eta_high_sec: Mapped[int | None] = mapped_column(Integer)
    family_track_token_hash: Mapped[str | None] = mapped_column(Text)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    at_scene_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    on_board_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hospital_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_hospital_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handed_off_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # B's domain code (clinical.py, selection.py) was written against a
    # single `acuity`/`facility` concept rather than the ai_*/final_* split
    # the real spec uses. Alias it: reads/writes the confirmed value once a
    # paramedic has confirmed triage, else falls back to the AI value --
    # matches technical.md's own intent (ai_* is the AI's guess, final_* is
    # what's actually acted on once confirmed) without rewriting every call
    # site that already uses `.acuity`.
    @property
    def acuity(self) -> str | None:
        return self.final_acuity or self.ai_acuity

    @acuity.setter
    def acuity(self, value: str | None) -> None:
        self.final_acuity = value

    @property
    def facility(self) -> str | None:
        return self.final_facility or self.ai_facility

    @facility.setter
    def facility(self, value: str | None) -> None:
        self.final_facility = value


class Patient(TimestampMixin, Base):
    """technical.md §5.4 — patients."""

    __tablename__ = "patients"

    emergency_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    temp_id: Mapped[str | None] = mapped_column(String(30))
    is_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    est_age: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(1))
    merged_into_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class FollowupAnswer(TimestampMixin, Base):
    """technical.md §5.4 — followup_answers."""

    __tablename__ = "followup_answers"

    emergency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"), nullable=False)
    question_id: Mapped[str] = mapped_column(String(50), nullable=False)
    answer_raw: Mapped[str | None] = mapped_column(Text)
    answer_parsed: Mapped[dict | None] = mapped_column(JSONB)
    language: Mapped[str | None] = mapped_column(String(10))


class TriageConfirmation(TimestampMixin, Base):
    """technical.md §5.4 — triage_confirmations (the learning loop's
    feedback source, technical.md §9.19)."""

    __tablename__ = "triage_confirmations"

    emergency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emergencies.id"), nullable=False)
    paramedic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    ai_acuity: Mapped[str | None] = mapped_column(String(20))
    ai_facility: Mapped[str | None] = mapped_column(String(20))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    final_acuity: Mapped[str | None] = mapped_column(String(20))
    final_facility: Mapped[str | None] = mapped_column(String(20))
    changed: Mapped[bool | None] = mapped_column(Boolean)
    input_text: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(50))
    used_for_training: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
