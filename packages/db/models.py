from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from packages.db.base import Base
from packages.db.enums import (
    ConfidenceStatus,
    ExportStatus,
    JobStatus,
    UserRole,
    VideoStatus,
)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


JsonType = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=UserRole.OPERATOR.value, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    sessions: Mapped[list[UserSession]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))

    user: Mapped[User] = relationship(back_populates="sessions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64))
    resource_id: Mapped[Optional[str]] = mapped_column(String(64))
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[Optional[User]] = relationship(back_populates="audit_logs")

    __table_args__ = (Index("ix_audit_logs_created_at", "created_at"),)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128))
    duration: Mapped[Optional[float]] = mapped_column(Float)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    fps: Mapped[Optional[float]] = mapped_column(Float)
    frame_count: Mapped[Optional[int]] = mapped_column(Integer)
    codec: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default=VideoStatus.READY.value, index=True)
    source_type: Mapped[str] = mapped_column(String(64), default="uploaded_video")
    source_id: Mapped[Optional[str]] = mapped_column(String(128))
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    jobs: Mapped[list[ProcessingJob]] = relationship(back_populates="video")
    created_by: Mapped[Optional[User]] = relationship(foreign_keys=[created_by_user_id])

    __table_args__ = (Index("ix_videos_created_at", "created_at"),)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    processing_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), default=_uuid, index=True)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.QUEUED.value, index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_frame: Mapped[int] = mapped_column(Integer, default=0)
    total_frames: Mapped[int] = mapped_column(Integer, default=0)
    processed_frames: Mapped[int] = mapped_column(Integer, default=0)
    skipped_frames: Mapped[int] = mapped_column(Integer, default=0)
    processing_fps: Mapped[Optional[float]] = mapped_column(Float)
    estimated_remaining_seconds: Mapped[Optional[float]] = mapped_column(Float)
    requested_device: Mapped[Optional[str]] = mapped_column(String(32))
    actual_device: Mapped[Optional[str]] = mapped_column(String(64))
    gpu_name: Mapped[Optional[str]] = mapped_column(String(256))
    model_versions: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonType)
    ocr_engine: Mapped[Optional[str]] = mapped_column(String(64))
    processing_profile: Mapped[str] = mapped_column(String(32), default="balanced")
    vehicles_detected: Mapped[int] = mapped_column(Integer, default=0)
    plates_detected: Mapped[int] = mapped_column(Integer, default=0)
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonType)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    fallback_reason: Mapped[Optional[str]] = mapped_column(String(128))
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(128))
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    video: Mapped[Video] = relationship(back_populates="jobs")
    created_by: Mapped[Optional[User]] = relationship(foreign_keys=[created_by_user_id])
    tracks: Mapped[list[VehicleTrack]] = relationship(back_populates="job", cascade="all, delete-orphan")
    assets: Mapped[list[MediaAsset]] = relationship(back_populates="job", cascade="all, delete-orphan")
    exports: Mapped[list[Export]] = relationship(back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_processing_jobs_created_at", "created_at"),)


class VehicleTrack(Base):
    __tablename__ = "vehicle_tracks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    processing_job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(64), default="unknown")
    first_frame: Mapped[int] = mapped_column(Integer, default=0)
    last_frame: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    last_seen_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    detection_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[ProcessingJob] = relationship(back_populates="tracks")
    plate_detections: Mapped[list[PlateDetection]] = relationship(
        back_populates="vehicle_track", cascade="all, delete-orphan"
    )


class PlateDetection(Base):
    __tablename__ = "plate_detections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    vehicle_track_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vehicle_tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_ocr_text: Mapped[Optional[str]] = mapped_column(String(64))
    normalized_plate_text: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    plate_detection_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default=ConfidenceStatus.UNCERTAIN.value)
    first_seen_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    last_seen_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    best_frame_number: Mapped[Optional[int]] = mapped_column(Integer)
    consistency_score: Mapped[Optional[float]] = mapped_column(Float)
    full_frame_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    vehicle_crop_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    plate_crop_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    vehicle_track: Mapped[VehicleTrack] = relationship(back_populates="plate_detections")
    observations: Mapped[list[Observation]] = relationship(
        back_populates="plate_detection", cascade="all, delete-orphan"
    )


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    plate_detection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("plate_detections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    raw_ocr_text: Mapped[Optional[str]] = mapped_column(String(64))
    normalized_plate_text: Mapped[Optional[str]] = mapped_column(String(64))
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    bounding_box: Mapped[Optional[dict[str, Any]]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plate_detection: Mapped[PlateDetection] = relationship(back_populates="observations")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    processing_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("processing_jobs.id", ondelete="CASCADE"), index=True
    )
    video_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), index=True
    )
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128))
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    checksum: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Optional[ProcessingJob]] = relationship(back_populates="assets")


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    processing_job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    export_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=ExportStatus.PENDING.value)
    storage_key: Mapped[Optional[str]] = mapped_column(String(1024))
    media_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[ProcessingJob] = relationship(back_populates="exports")
