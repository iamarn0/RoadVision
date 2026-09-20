from pathlib import Path

import pytest

from app.config import Settings
from app.core.errors import AppError
from app.services.video_validation import validate_upload
from app.storage.service import LocalStorageService


def test_validate_upload_rejects_bad_extension() -> None:
    with pytest.raises(AppError) as exc:
        validate_upload("notes.txt", "text/plain", 100)
    assert exc.value.error_code == "VIDEO_UNSUPPORTED"


def test_validate_upload_rejects_empty() -> None:
    with pytest.raises(AppError) as exc:
        validate_upload("clip.mp4", "video/mp4", 0)
    assert exc.value.error_code == "VIDEO_INVALID"


def test_local_storage_rejects_traversal(tmp_path: Path) -> None:
    storage = LocalStorageService(Settings(storage_root=str(tmp_path)))
    with pytest.raises(AppError):
        storage.get_path("../etc/passwd")


def test_local_storage_roundtrip(tmp_path: Path) -> None:
    storage = LocalStorageService(Settings(storage_root=str(tmp_path)))
    key = storage.save("uploads", "demo.mp4", b"abc123")
    assert storage.exists(key)
    assert storage.file_size(key) == 6
    assert ".." not in key
    storage.delete(key)
    assert not storage.exists(key)
