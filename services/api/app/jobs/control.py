from uuid import UUID

import redis

from app.config import get_settings

CANCEL_KEY = "roadvision:job:cancel:{job_id}"
PAUSE_KEY = "roadvision:job:pause:{job_id}"
CAPTURE_KEY = "roadvision:job:capture:{job_id}"
CAPTURE_RESULT_KEY = "roadvision:job:capture-result:{job_id}"
PROGRESS_CHANNEL = "roadvision:job:progress"
FLAG_TTL_SECONDS = 86400


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def request_cancel(job_id: UUID) -> None:
    redis_client().set(CANCEL_KEY.format(job_id=job_id), "1", ex=FLAG_TTL_SECONDS)


def is_cancelled(job_id: str) -> bool:
    return redis_client().get(CANCEL_KEY.format(job_id=job_id)) == "1"


def clear_cancel(job_id: UUID) -> None:
    redis_client().delete(CANCEL_KEY.format(job_id=job_id))


def request_pause(job_id: UUID) -> None:
    redis_client().set(PAUSE_KEY.format(job_id=job_id), "1", ex=FLAG_TTL_SECONDS)


def is_paused(job_id: UUID | str) -> bool:
    try:
        return redis_client().get(PAUSE_KEY.format(job_id=job_id)) == "1"
    except Exception:
        return False


def clear_pause(job_id: UUID) -> None:
    redis_client().delete(PAUSE_KEY.format(job_id=job_id))


def request_capture(job_id: UUID) -> None:
    client = redis_client()
    client.delete(CAPTURE_RESULT_KEY.format(job_id=job_id))
    client.set(CAPTURE_KEY.format(job_id=job_id), "1", ex=FLAG_TTL_SECONDS)


def clear_capture(job_id: UUID) -> None:
    client = redis_client()
    client.delete(CAPTURE_KEY.format(job_id=job_id))
    client.delete(CAPTURE_RESULT_KEY.format(job_id=job_id))


def wait_capture_result(job_id: UUID, timeout_seconds: float = 1.5) -> str | None:
    import time

    key = CAPTURE_RESULT_KEY.format(job_id=job_id)
    deadline = time.perf_counter() + timeout_seconds
    client = redis_client()
    while time.perf_counter() < deadline:
        value = client.get(key)
        if value:
            return str(value)
        time.sleep(0.05)
    return None


def clear_job_flags(job_id: UUID) -> None:
    client = redis_client()
    client.delete(
        CANCEL_KEY.format(job_id=job_id),
        PAUSE_KEY.format(job_id=job_id),
        CAPTURE_KEY.format(job_id=job_id),
        CAPTURE_RESULT_KEY.format(job_id=job_id),
    )
