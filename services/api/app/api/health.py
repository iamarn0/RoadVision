from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.config import get_settings
from app.database import get_engine
from app.security.deps import RequireReader

router = APIRouter(tags=["health"])


@router.get("/health/live", summary="Liveness probe")
def live() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "api",
        "version": settings.app_version,
    }


@router.get("/health/ready", summary="Readiness probe")
def ready(_: RequireReader, response: Response) -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, str] = {}
    ready_flag = True

    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "unavailable"
        ready_flag = False

    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
        ready_flag = False

    storage = Path(settings.storage_root)
    if storage.exists():
        checks["storage"] = "ok"
    else:
        checks["storage"] = "unavailable"
        ready_flag = False

    if not ready_flag:
        response.status_code = 503

    return {
        "status": "ok" if ready_flag else "degraded",
        "checks": checks,
        "version": settings.app_version,
    }


@router.get("/metrics", summary="Basic process metrics")
def metrics(_: RequireReader) -> dict[str, object]:
    settings = get_settings()
    return {
        "service": "api",
        "version": settings.app_version,
        "timestamp": datetime.now(UTC).isoformat(),
    }
