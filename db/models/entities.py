from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base

VECTOR_DIMENSION = 512


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    primary_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("face_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    samples: Mapped[list["FaceSample"]] = relationship(back_populates="person", foreign_keys="FaceSample.person_id")
    templates: Mapped[list["FaceTemplate"]] = relationship(back_populates="person", foreign_keys="FaceTemplate.person_id")
    primary_template: Mapped["FaceTemplate | None"] = relationship(foreign_keys=[primary_template_id], uselist=False, post_update=True)


class DeviceConfig(Base):
    __tablename__ = "device_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_name: Mapped[str] = mapped_column(String(255))
    location_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    det_thresh: Mapped[float] = mapped_column(Float, default=0.60, server_default="0.60")
    det_size_width: Mapped[int] = mapped_column(Integer, default=320, server_default="320")
    det_size_height: Mapped[int] = mapped_column(Integer, default=320, server_default="320")
    max_faces: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    min_face_width_px: Mapped[int] = mapped_column(Integer, default=160, server_default="160")
    min_brightness: Mapped[float] = mapped_column(Float, default=75.0, server_default="75")
    min_blur_score: Mapped[float] = mapped_column(Float, default=90.0, server_default="90")
    similarity_threshold: Mapped[float] = mapped_column(Float, default=0.45, server_default="0.45")
    liveness_threshold: Mapped[float] = mapped_column(Float, default=0.70, server_default="0.70")
    multi_frame_confirm: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    accepted_per_pose: Mapped[int] = mapped_column(Integer, default=4, server_default="4")
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_name: Mapped[str] = mapped_column(String(255))
    session_kind: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    logs: Mapped[list["AttendanceLog"]] = relationship(back_populates="session")


class FaceSample(Base):
    __tablename__ = "face_samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"))
    enrollment_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    pose: Mapped[str] = mapped_column(String(32), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIMENSION))
    image_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_device_code: Mapped[str] = mapped_column(String(64))
    brightness_score: Mapped[float] = mapped_column(Float)
    blur_score: Mapped[float] = mapped_column(Float)
    liveness_score: Mapped[float] = mapped_column(Float)
    face_width_px: Mapped[int] = mapped_column(Integer)
    quality_flags: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    person: Mapped["Person"] = relationship(back_populates="samples", foreign_keys=[person_id])


class FaceTemplate(Base):
    __tablename__ = "face_templates"
    __table_args__ = (
        UniqueConstraint("person_id", "version", name="uq_face_templates_person_version"),
        Index(
            "ix_face_templates_one_active_per_person",
            "person_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIMENSION))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    sample_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    built_from_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    person: Mapped["Person"] = relationship(back_populates="templates", foreign_keys=[person_id])


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True, index=True)
    matched_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("face_templates.id", ondelete="SET NULL"), nullable=True)
    device_code: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    session: Mapped["AttendanceSession | None"] = relationship(back_populates="logs")
