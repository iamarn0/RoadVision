from pathlib import Path

from packages.app_meta import read_app_version

REQUIRED_ENV_KEYS = [
    "APP_VERSION",
    "PROCESSING_DEVICE",
    "CUDA_DEVICE",
    "USE_HALF_PRECISION",
    "AUTO_FALLBACK_TO_CPU",
    "VEHICLE_MODEL_PATH",
    "PLATE_MODEL_PATH",
    "VEHICLE_CONFIDENCE",
    "PLATE_CONFIDENCE",
    "INFERENCE_BATCH_SIZE",
    "MAX_WORKERS",
    "OCR_ENGINE",
    "OCR_DEVICE",
    "RETENTION_DAYS",
    "DATABASE_URL",
    "REDIS_URL",
    "AUTH_DISABLED",
    "BOOTSTRAP_ADMIN_EMAIL",
    "SESSION_COOKIE_NAME",
]


def test_env_example_contains_required_keys() -> None:
    root = Path(__file__).resolve().parents[3]
    text = (root / ".env.example").read_text(encoding="utf-8")
    missing = [key for key in REQUIRED_ENV_KEYS if f"{key}=" not in text]
    assert missing == [], f"Missing keys in .env.example: {missing}"


def test_application_version_is_010() -> None:
    from app import APP_VERSION

    assert APP_VERSION == read_app_version()
    assert read_app_version() != "unknown"
