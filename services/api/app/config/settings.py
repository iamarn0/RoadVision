from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for path in [here.parent, *here.parents]:
        if (path / "packages").is_dir():
            return path
    return here.parents[min(4, len(list(here.parents)) - 1)]


_REPO_ROOT = _find_repo_root()
_PLACEHOLDER_SECRET = "change-me-in-development"
_ENV_CANDIDATES = (
    Path(".env"),
    _REPO_ROOT / ".env",
)


def _env_files() -> tuple[str, ...]:
    return tuple(str(path) for path in _ENV_CANDIDATES if path.is_file())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files() or (".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "RoadVision"
    app_version: str = "0.1.0"
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"
    secret_key: str = _PLACEHOLDER_SECRET
    auth_disabled: bool = False
    session_cookie_name: str = "roadvision_session"
    session_ttl_seconds: int = 604_800
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_name: str = "Administrator"
    login_max_attempts: int = 5
    login_lockout_seconds: int = 300

    database_url: str = "sqlite:///./storage/roadvision.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    max_queue_size: int = 100
    max_workers: int = 1
    stale_job_timeout_seconds: int = 900

    storage_backend: str = "local"
    storage_root: str = "./storage"
    retention_days: int = 30
    max_upload_bytes: int = 2_147_483_648
    allowed_video_extensions: str = "mp4,avi,mov,mkv,webm"
    allowed_video_mime_types: str = (
        "video/mp4,video/x-msvideo,video/quicktime,video/x-matroska,video/webm,application/octet-stream"
    )

    processing_device: str = "auto"
    cuda_device: int = 0
    use_half_precision: bool = True
    auto_fallback_to_cpu: bool = False
    ocr_device: str = "auto"

    vehicle_model_path: str = "./models/vehicle_detector.pt"
    plate_model_path: str = "./models/plate_detector.pt"
    vehicle_model_version: str = "unconfigured"
    plate_model_version: str = "unconfigured"

    vehicle_confidence: float = 0.35
    plate_confidence: float = 0.25
    iou_threshold: float = 0.45
    inference_image_size: int = 640
    inference_batch_size: int = 1
    frame_skip: int = 0
    max_processing_fps: float = 15.0
    processing_profile: str = "balanced"

    ocr_engine: str = "easyocr"
    ocr_languages: str = "en"
    ocr_interval_frames: int = 3
    high_confidence_threshold: float = 0.85
    medium_confidence_threshold: float = 0.65
    low_confidence_threshold: float = 0.40
    display_plate_threshold: float = 0.65

    default_source_type: str = "uploaded_video"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def allowed_extensions_set(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.allowed_video_extensions.split(",") if e.strip()}

    @property
    def allowed_mime_set(self) -> set[str]:
        return {m.strip().lower() for m in self.allowed_video_mime_types.split(",") if m.strip()}

    @property
    def storage_root_path(self) -> Path:
        root = Path(self.storage_root)
        if not root.is_absolute():
            root = _REPO_ROOT / root
        return root.resolve()

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = _REPO_ROOT / path
        return path.resolve()

    @property
    def resolved_vehicle_model_path(self) -> Path:
        return self.resolve_path(self.vehicle_model_path)

    @property
    def resolved_plate_model_path(self) -> Path:
        return self.resolve_path(self.plate_model_path)

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url
        if not url.startswith("sqlite:///"):
            return url
        raw = url.removeprefix("sqlite:///")
        if raw.startswith(":memory:") or Path(raw).is_absolute():
            return url
        return f"sqlite:///{(_REPO_ROOT / raw).resolve().as_posix()}"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    def validate_runtime(self) -> None:
        if self.is_production and self.auth_disabled:
            raise RuntimeError("AUTH_DISABLED cannot be true when APP_ENV=production")
        if self.is_production and self.secret_key == _PLACEHOLDER_SECRET:
            raise RuntimeError("SECRET_KEY must be changed before production deployment")


@lru_cache
def get_settings() -> Settings:
    return Settings()
