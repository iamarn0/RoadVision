from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.app_meta import read_app_version, read_git_commit


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for path in [here.parent, *here.parents]:
        if (path / "packages").is_dir():
            return path
    return here.parents[min(3, len(list(here.parents)) - 1)]


_REPO_ROOT = _find_repo_root()
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

    git_commit: str = Field(default_factory=read_git_commit)
    log_level: str = "INFO"
    database_url: str = "sqlite:///./storage/roadvision.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    storage_root: str = "./storage"
    storage_backend: str = "local"
    max_workers: int = 1
    stale_job_timeout_seconds: int = 900

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def app_version(self) -> str:
        return read_app_version()

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


PROFILES = {
    "balanced": {"inference_image_size": 640, "frame_skip": 0, "ocr_interval_frames": 3, "use_half_precision": True},
    "performance": {"inference_image_size": 512, "frame_skip": 1, "ocr_interval_frames": 5, "use_half_precision": True},
    "accuracy": {"inference_image_size": 960, "frame_skip": 0, "ocr_interval_frames": 1, "use_half_precision": True},
    "custom": {},
}


@lru_cache
def get_settings() -> Settings:
    return Settings()
