"""Initial RoadVision schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-09-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False, unique=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("mime_type", sa.String(128)),
        sa.Column("duration", sa.Float()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("fps", sa.Float()),
        sa.Column("frame_count", sa.Integer()),
        sa.Column("codec", sa.String(64)),
        sa.Column("status", sa.String(32), nullable=False, server_default="ready"),
        sa.Column("source_type", sa.String(64), server_default="uploaded_video"),
        sa.Column("source_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_videos_status", "videos", ["status"])
    op.create_index("ix_videos_created_at", "videos", ["created_at"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("processing_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Float(), server_default="0"),
        sa.Column("current_frame", sa.Integer(), server_default="0"),
        sa.Column("total_frames", sa.Integer(), server_default="0"),
        sa.Column("processed_frames", sa.Integer(), server_default="0"),
        sa.Column("skipped_frames", sa.Integer(), server_default="0"),
        sa.Column("processing_fps", sa.Float()),
        sa.Column("estimated_remaining_seconds", sa.Float()),
        sa.Column("requested_device", sa.String(32)),
        sa.Column("actual_device", sa.String(64)),
        sa.Column("gpu_name", sa.String(256)),
        sa.Column("model_versions", postgresql.JSONB()),
        sa.Column("ocr_engine", sa.String(64)),
        sa.Column("processing_profile", sa.String(32), server_default="balanced"),
        sa.Column("vehicles_detected", sa.Integer(), server_default="0"),
        sa.Column("plates_detected", sa.Integer(), server_default="0"),
        sa.Column("metrics", postgresql.JSONB()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.Text()),
        sa.Column("fallback_reason", sa.String(128)),
        sa.Column("celery_task_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_processing_jobs_video_id", "processing_jobs", ["video_id"])
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])
    op.create_index("ix_processing_jobs_created_at", "processing_jobs", ["created_at"])
    op.create_index("ix_processing_jobs_processing_run_id", "processing_jobs", ["processing_run_id"])

    op.create_table(
        "vehicle_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("processing_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_type", sa.String(64), server_default="unknown"),
        sa.Column("first_frame", sa.Integer(), server_default="0"),
        sa.Column("last_frame", sa.Integer(), server_default="0"),
        sa.Column("first_seen_seconds", sa.Float(), server_default="0"),
        sa.Column("last_seen_seconds", sa.Float(), server_default="0"),
        sa.Column("detection_confidence", sa.Float(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_vehicle_tracks_processing_job_id", "vehicle_tracks", ["processing_job_id"])

    op.create_table(
        "plate_detections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_track_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicle_tracks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_ocr_text", sa.String(64)),
        sa.Column("normalized_plate_text", sa.String(64)),
        sa.Column("ocr_confidence", sa.Float(), server_default="0"),
        sa.Column("plate_detection_confidence", sa.Float(), server_default="0"),
        sa.Column("status", sa.String(32), server_default="uncertain"),
        sa.Column("first_seen_seconds", sa.Float(), server_default="0"),
        sa.Column("last_seen_seconds", sa.Float(), server_default="0"),
        sa.Column("best_frame_number", sa.Integer()),
        sa.Column("consistency_score", sa.Float()),
        sa.Column("full_frame_asset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("vehicle_crop_asset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("plate_crop_asset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_plate_detections_vehicle_track_id", "plate_detections", ["vehicle_track_id"])
    op.create_index("ix_plate_detections_normalized_plate_text", "plate_detections", ["normalized_plate_text"])

    op.create_table(
        "observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plate_detection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plate_detections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("frame_number", sa.Integer(), nullable=False),
        sa.Column("timestamp_seconds", sa.Float(), server_default="0"),
        sa.Column("raw_ocr_text", sa.String(64)),
        sa.Column("normalized_plate_text", sa.String(64)),
        sa.Column("ocr_confidence", sa.Float(), server_default="0"),
        sa.Column("bounding_box", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_observations_plate_detection_id", "observations", ["plate_detection_id"])

    op.create_table(
        "media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("processing_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("processing_jobs.id", ondelete="CASCADE")),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE")),
        sa.Column("asset_type", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("mime_type", sa.String(128)),
        sa.Column("file_size", sa.BigInteger(), server_default="0"),
        sa.Column("checksum", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_media_assets_processing_job_id", "media_assets", ["processing_job_id"])
    op.create_index("ix_media_assets_video_id", "media_assets", ["video_id"])

    op.create_table(
        "exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("processing_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("export_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("storage_key", sa.String(1024)),
        sa.Column("media_asset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_exports_processing_job_id", "exports", ["processing_job_id"])


def downgrade() -> None:
    op.drop_table("exports")
    op.drop_table("media_assets")
    op.drop_table("observations")
    op.drop_table("plate_detections")
    op.drop_table("vehicle_tracks")
    op.drop_table("processing_jobs")
    op.drop_table("videos")
