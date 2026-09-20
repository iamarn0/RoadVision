from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.database import get_engine
from app.security.deps import RequireReader
from packages.device.probe import probe_gpu

router = APIRouter(prefix="/api/system", tags=["system"])


def _status(ok: bool, missing: bool = False) -> str:
    if missing:
        return "unknown"
    return "healthy" if ok else "critical"


@router.get("/health", summary="Aggregated system health")
def system_health(_: RequireReader) -> dict[str, object]:
    settings = get_settings()
    gpu = probe_gpu(settings.processing_device, settings.cuda_device, settings.use_half_precision)

    postgres = "unknown"
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        postgres = "healthy"
    except Exception:
        postgres = "critical"

    redis_status = "unknown"
    queue_depth = None
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        client.ping()
        redis_status = "healthy"
        queue_depth = int(client.llen("celery"))
    except Exception:
        redis_status = "critical"

    vehicle_path = settings.resolved_vehicle_model_path
    plate_path = settings.resolved_plate_model_path

    storage_ok = settings.storage_root_path.exists()

    return {
        "application": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
        },
        "infrastructure": {
            "api": "healthy",
            "postgres": postgres,
            "redis": redis_status,
            "worker": "unknown",
            "storage": "healthy" if storage_ok else "critical",
        },
        "ai": {
            "vehicle_model": "configured" if vehicle_path.is_file() else "not_configured",
            "vehicle_model_path": str(vehicle_path),
            "plate_model": "configured" if plate_path.is_file() else "not_configured",
            "plate_model_path": str(plate_path),
            "ocr": settings.ocr_engine,
            "tracker": "bytetrack",
        },
        "hardware": {
            "gpu": gpu,
        },
        "performance": {
            "queue_depth": queue_depth,
            "gpu_memory_mb": gpu.get("available_memory_mb"),
            "processing_fps": None,
            "inference_latency": None,
            "ocr_latency": None,
        },
    }


@router.get("/gpu", summary="Runtime GPU diagnostics")
def gpu_status(_: RequireReader) -> dict[str, object]:
    settings = get_settings()
    return probe_gpu(settings.processing_device, settings.cuda_device, settings.use_half_precision)
