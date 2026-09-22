from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VideoRead(ORMModel):
    id: UUID
    original_filename: str
    file_size: int
    mime_type: Optional[str]
    duration: Optional[float]
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    frame_count: Optional[int]
    codec: Optional[str]
    status: str
    source_type: str
    original_asset_id: Optional[UUID] = None
    district_id: Optional[UUID] = None
    district_name: Optional[str] = None
    created_at: datetime


class ProcessJobRequest(BaseModel):
    processing_profile: str = "balanced"
    inference_image_size: Optional[int] = None
    frame_skip: Optional[int] = None
    ocr_interval_frames: Optional[int] = None
    vehicle_confidence: Optional[float] = None
    plate_confidence: Optional[float] = None


class JobRead(ORMModel):
    id: UUID
    video_id: UUID
    processing_run_id: UUID
    status: str
    progress: float
    current_frame: int
    total_frames: int
    processed_frames: int
    skipped_frames: int
    processing_fps: Optional[float]
    estimated_remaining_seconds: Optional[float]
    requested_device: Optional[str]
    actual_device: Optional[str]
    gpu_name: Optional[str]
    model_versions: Optional[dict[str, Any]]
    ocr_engine: Optional[str]
    processing_profile: str
    vehicles_detected: int
    plates_detected: int
    metrics: Optional[dict[str, Any]]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_code: Optional[str]
    error_message: Optional[str]
    fallback_reason: Optional[str]
    created_at: datetime
    source_filename: Optional[str] = None
    annotated_asset_id: Optional[UUID] = None
    original_asset_id: Optional[UUID] = None
    source_fps: Optional[float] = None
    live_frame_available: bool = False
    paused: bool = False
    district_id: Optional[UUID] = None
    district_name: Optional[str] = None


class LiveCaptureItem(BaseModel):
    track_id: int
    plate_url: str
    vehicle_url: str
    full_url: Optional[str] = None
    updated_at: float
    kind: str = "plate"
    label: Optional[str] = None
    vehicle_type: Optional[str] = None
    first_seen_seconds: Optional[float] = None
    last_seen_seconds: Optional[float] = None
    timestamp: Optional[float] = None
    timestamp_overlay: Optional[str] = None
    last_seen_overlay: Optional[str] = None
    plate_confidence: Optional[float] = None
    vehicle_confidence: Optional[float] = None
    plate_width: Optional[float] = None
    good_evidence: Optional[bool] = None


class LiveCapturesResponse(BaseModel):
    job_id: str
    plates_captured: int
    items: list[LiveCaptureItem]


class CaptureJobResponse(JobRead):
    snapshot: Optional[LiveCaptureItem] = None


class ObservationRead(ORMModel):
    id: UUID
    frame_number: int
    timestamp_seconds: float
    raw_ocr_text: Optional[str]
    normalized_plate_text: Optional[str]
    ocr_confidence: float
    bounding_box: Optional[dict[str, Any]]


class DetectionRead(ORMModel):
    id: UUID
    track_id: int
    vehicle_type: str
    vehicle_track_id: UUID
    raw_ocr_text: Optional[str]
    normalized_plate_text: Optional[str]
    ocr_confidence: float
    plate_detection_confidence: float
    vehicle_detection_confidence: float
    status: str
    first_seen_seconds: float
    last_seen_seconds: float
    first_seen_overlay: Optional[str] = None
    last_seen_overlay: Optional[str] = None
    best_frame_number: Optional[int]
    consistency_score: Optional[float]
    full_frame_asset_id: Optional[UUID]
    vehicle_crop_asset_id: Optional[UUID]
    plate_crop_asset_id: Optional[UUID]


class DetectionDetail(DetectionRead):
    observations: list[ObservationRead] = Field(default_factory=list)


class PaginatedDetections(BaseModel):
    items: list[DetectionRead]
    total: int
    page: int
    page_size: int


class PaginatedObservations(BaseModel):
    items: list[ObservationRead]
    total: int
    page: int
    page_size: int


class JobResults(BaseModel):
    job: JobRead
    unique_vehicles: int
    unique_plates: int
    detections: PaginatedDetections


class DashboardMetrics(BaseModel):
    videos_processed: int
    processing_jobs: int
    vehicles_detected: int
    unique_plates: int
    active_jobs: list[JobRead]
    recent_videos: list[VideoRead]
    recent_detections: list[DetectionRead]


class ExportRead(ORMModel):
    id: UUID
    processing_job_id: UUID
    export_type: str
    status: str
    media_asset_id: Optional[UUID]
    error_message: Optional[str]
    created_at: datetime


class SettingsPublic(BaseModel):
    app_version: str
    git_commit: str
    environment: str
    processing_profile: str
    inference_image_size: int
    frame_skip: int
    ocr_interval_frames: int
    vehicle_confidence: float
    plate_confidence: float
    high_confidence_threshold: float
    medium_confidence_threshold: float
    processing_device: str
    use_half_precision: bool
    ocr_engine: str
    storage_backend: str
    retention_days: int
    vehicle_model_configured: bool
    plate_model_configured: bool
    authentication_enabled: bool
