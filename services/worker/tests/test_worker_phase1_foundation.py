from pathlib import Path


def test_job_progress_schema_exists() -> None:
    root = Path(__file__).resolve().parents[3]
    schema = root / "packages" / "contracts" / "event-schemas" / "job-progress.json"
    assert schema.is_file()
    text = schema.read_text(encoding="utf-8")
    assert "processing_fps" in text
    assert "current_frame" in text


def test_worker_version() -> None:
    from app import APP_VERSION

    assert APP_VERSION == "0.1.0"
