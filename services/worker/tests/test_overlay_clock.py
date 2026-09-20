from datetime import datetime

from packages.overlay_clock import (
    format_overlay_datetime,
    origin_from_sample,
    overlay_at,
    overlay_label,
    parse_overlay_datetime,
)


def test_parse_cctv_overlay_timestamp() -> None:
    parsed = parse_overlay_datetime("18-09-2026 08:33:32 PM")
    assert parsed == datetime(2026, 9, 18, 20, 33, 32)


def test_parse_dotted_overlay_time() -> None:
    parsed = parse_overlay_datetime("18-09-2026 08.33.29 PM")
    assert parsed == datetime(2026, 9, 18, 20, 33, 29)


def test_parse_does_not_corrupt_zero_minutes() -> None:
    parsed = parse_overlay_datetime("18-09-2026 10:00:00 PM")
    assert parsed == datetime(2026, 9, 18, 22, 0, 0)


def test_parse_handles_ocr_noise() -> None:
    parsed = parse_overlay_datetime("Date 18-09-2026 Time 08:33:32PM")
    assert parsed == datetime(2026, 9, 18, 20, 33, 32)


def test_format_matches_camera_overlay() -> None:
    assert format_overlay_datetime(datetime(2026, 9, 18, 20, 33, 32)) == "18-09-2026 08:33:32 PM"


def test_overlay_at_offsets_from_video_time() -> None:
    origin = origin_from_sample(datetime(2026, 9, 18, 20, 33, 32), 0.0)
    assert overlay_at(origin, 110) == "18-09-2026 08:35:22 PM"


def test_overlay_label_from_job_metrics() -> None:
    metrics = {"overlay_clock": {"origin_iso": "2026-09-18T20:33:32"}}
    assert overlay_label(metrics, 2) == "18-09-2026 08:33:34 PM"
    assert overlay_label(metrics, 0) == "18-09-2026 08:33:32 PM"
    assert overlay_label({}, 2) is None


def test_parse_iso_overlay_timestamp() -> None:
    parsed = parse_overlay_datetime("2025-09-20 13:48:13 PM")
    assert parsed == datetime(2025, 9, 20, 13, 48, 13)


def test_parse_iso_does_not_become_day_month() -> None:
    parsed = parse_overlay_datetime("2026-09-20 01:48:13 PM")
    assert parsed == datetime(2026, 9, 20, 13, 48, 13)


def test_parse_24h_with_pm_keeps_hour() -> None:
    parsed = parse_overlay_datetime("20-09-2026 13:48:13 PM")
    assert parsed == datetime(2026, 9, 20, 13, 48, 13)
