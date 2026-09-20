"""Login attempt rate limiting (Redis with in-memory fallback)."""

from __future__ import annotations

import threading
import time
from typing import Optional

from app.config import get_settings
from app.core.errors import AppError, ErrorCodes

_lock = threading.Lock()
_memory: dict[str, tuple[int, float]] = {}


def _redis_client():
    try:
        import redis

        settings = get_settings()
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.5)
        client.ping()
        return client
    except Exception:
        return None


def _key(kind: str, value: str) -> str:
    return f"roadvision:login:{kind}:{value.lower()}"


def check_login_allowed(*, ip: Optional[str], email: str) -> None:
    settings = get_settings()
    for kind, value in (("ip", ip or "unknown"), ("email", email)):
        count = _get_count(kind, value)
        if count >= settings.login_max_attempts:
            raise AppError(
                ErrorCodes.RATE_LIMITED,
                "Too many login attempts. Try again later.",
                status_code=429,
            )


def record_login_failure(*, ip: Optional[str], email: str) -> None:
    settings = get_settings()
    for kind, value in (("ip", ip or "unknown"), ("email", email)):
        _incr(kind, value, settings.login_lockout_seconds)


def clear_login_failures(*, ip: Optional[str], email: str) -> None:
    for kind, value in (("ip", ip or "unknown"), ("email", email)):
        _clear(kind, value)


def _get_count(kind: str, value: str) -> int:
    client = _redis_client()
    key = _key(kind, value)
    if client is not None:
        try:
            raw = client.get(key)
            return int(raw) if raw else 0
        except Exception:
            pass
    with _lock:
        entry = _memory.get(key)
        if not entry:
            return 0
        count, expires = entry
        if expires < time.time():
            del _memory[key]
            return 0
        return count


def _incr(kind: str, value: str, ttl: int) -> None:
    client = _redis_client()
    key = _key(kind, value)
    if client is not None:
        try:
            count = client.incr(key)
            if count == 1:
                client.expire(key, ttl)
            return
        except Exception:
            pass
    with _lock:
        now = time.time()
        entry = _memory.get(key)
        if not entry or entry[1] < now:
            _memory[key] = (1, now + ttl)
        else:
            _memory[key] = (entry[0] + 1, entry[1])


def _clear(kind: str, value: str) -> None:
    client = _redis_client()
    key = _key(kind, value)
    if client is not None:
        try:
            client.delete(key)
        except Exception:
            pass
    with _lock:
        _memory.pop(key, None)
