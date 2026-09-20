"""Parse and format burned-in CCTV overlay clocks (top of frame)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional

_TIME = r"(?P<h>\d{1,2})[:.](?P<mi>\d{2})[:.](?P<s>\d{2})(?:\s*(?P<p>AM|PM))?"
_YMD_RE = re.compile(
    rf"(?P<y>\d{{4}})[-/. ](?P<mo>\d{{1,2}})[-/. ](?P<d>\d{{1,2}})\D+{_TIME}",
    re.IGNORECASE,
)
_DMY_RE = re.compile(
    rf"(?P<d>\d{{1,2}})[-/. ](?P<mo>\d{{1,2}})[-/. ](?P<y>\d{{2,4}})\D+{_TIME}",
    re.IGNORECASE,
)


def normalize_overlay_text(text: str) -> str:
    cleaned = text.upper().replace(",", " ").replace("|", "1")
    cleaned = re.sub(r"O(?=\d)", "0", cleaned)
    cleaned = re.sub(r"(?<=\d)O", "0", cleaned)
    cleaned = re.sub(r"(?<=\d)L(?=\d)", "1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _hour_from_match(match: re.Match[str]) -> Optional[int]:
    hour = int(match.group("h"))
    meridiem = (match.group("p") or "").upper()
    if hour > 23:
        return None
    if meridiem == "PM" and hour < 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    return hour


def parse_overlay_datetime(text: str) -> Optional[datetime]:
    if not text:
        return None
    cleaned = normalize_overlay_text(text)
    candidates: list[re.Match[str]] = []
    ymd = _YMD_RE.search(cleaned)
    if ymd:
        candidates.append(ymd)
    dmy = _DMY_RE.search(cleaned)
    if dmy:
        start = dmy.start()
        year_token = dmy.group("y")
        swallowed_iso = len(year_token) == 2 and start > 0 and cleaned[start - 1].isdigit()
        if not swallowed_iso:
            candidates.append(dmy)
    for match in candidates:
        day = int(match.group("d"))
        month = int(match.group("mo"))
        year = int(match.group("y"))
        if year < 100:
            year += 2000
        hour = _hour_from_match(match)
        if hour is None:
            continue
        minute = int(match.group("mi"))
        second = int(match.group("s"))
        try:
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            continue
    return None


def format_overlay_datetime(value: datetime) -> str:
    hour12 = value.hour % 12 or 12
    meridiem = "AM" if value.hour < 12 else "PM"
    return (
        f"{value.day:02d}-{value.month:02d}-{value.year:04d} "
        f"{hour12:02d}:{value.minute:02d}:{value.second:02d} {meridiem}"
    )


def origin_from_sample(sample: datetime, sample_video_seconds: float) -> datetime:
    return sample - timedelta(seconds=max(0.0, float(sample_video_seconds)))


def overlay_at(origin: datetime, video_seconds: float) -> str:
    return format_overlay_datetime(origin + timedelta(seconds=float(video_seconds or 0.0)))


def overlay_clock_payload(origin: datetime, raw: str, sample_video_seconds: float) -> dict[str, Any]:
    return {
        "origin_iso": origin.isoformat(timespec="seconds"),
        "sample_raw": raw,
        "sample_video_seconds": float(sample_video_seconds),
        "display_pattern": "dd-mm-yyyy hh:mm:ss AM/PM",
    }


def origin_from_metrics(metrics: Optional[dict[str, Any]]) -> Optional[datetime]:
    clock = (metrics or {}).get("overlay_clock") if isinstance(metrics, dict) else None
    if not isinstance(clock, dict):
        return None
    raw = clock.get("origin_iso")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def overlay_label(metrics: Optional[dict[str, Any]], video_seconds: float) -> Optional[str]:
    origin = origin_from_metrics(metrics)
    if origin is None:
        return None
    return overlay_at(origin, video_seconds)
