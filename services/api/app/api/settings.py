from fastapi import APIRouter

from app.config import get_settings
from app.schemas.common import SettingsPublic
from app.security.deps import RequireReader

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsPublic)
def public_settings(_: RequireReader) -> SettingsPublic:
    settings = get_settings()
    return SettingsPublic(
        app_version=settings.app_version,
        git_commit=settings.git_commit,
        environment=settings.app_env,
        processing_profile=settings.processing_profile,
        inference_image_size=settings.inference_image_size,
        frame_skip=settings.frame_skip,
        ocr_interval_frames=settings.ocr_interval_frames,
        vehicle_confidence=settings.vehicle_confidence,
        plate_confidence=settings.plate_confidence,
        high_confidence_threshold=settings.high_confidence_threshold,
        medium_confidence_threshold=settings.medium_confidence_threshold,
        processing_device=settings.processing_device,
        use_half_precision=settings.use_half_precision,
        ocr_engine=settings.ocr_engine,
        storage_backend=settings.storage_backend,
        retention_days=settings.retention_days,
        vehicle_model_configured=settings.resolved_vehicle_model_path.is_file(),
        plate_model_configured=settings.resolved_plate_model_path.is_file(),
        authentication_enabled=not settings.auth_disabled,
    )
