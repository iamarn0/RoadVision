from __future__ import annotations

import hashlib
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.errors import AppError, ErrorCodes


class StorageService(ABC):
    @abstractmethod
    def save(self, category: str, filename: str, data: BinaryIO | bytes) -> str:
        ...

    @abstractmethod
    def get_path(self, storage_key: str) -> Path:
        ...

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        ...

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        ...

    @abstractmethod
    def file_size(self, storage_key: str) -> int:
        ...


class LocalStorageService(StorageService):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.root = self.settings.storage_root_path
        for sub in ("uploads", "processed", "evidence", "exports"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def _safe_join(self, storage_key: str) -> Path:
        if ".." in storage_key.replace("\\", "/").split("/"):
            raise AppError(ErrorCodes.STORAGE_ERROR, "Invalid storage key", status_code=400)
        path = (self.root / storage_key).resolve()
        if not str(path).startswith(str(self.root)):
            raise AppError(ErrorCodes.STORAGE_ERROR, "Path traversal rejected", status_code=400)
        return path

    def save(self, category: str, filename: str, data: BinaryIO | bytes) -> str:
        safe_name = Path(filename).name.replace(" ", "_")
        storage_key = f"{category}/{uuid4().hex}_{safe_name}"
        path = self._safe_join(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            with path.open("wb") as f:
                shutil.copyfileobj(data, f)
        return storage_key

    def get_path(self, storage_key: str) -> Path:
        path = self._safe_join(storage_key)
        if not path.exists():
            raise AppError(ErrorCodes.NOT_FOUND, "Media asset not found", status_code=404)
        return path

    def delete(self, storage_key: str) -> None:
        path = self._safe_join(storage_key)
        if path.exists():
            path.unlink()

    def exists(self, storage_key: str) -> bool:
        try:
            return self._safe_join(storage_key).exists()
        except AppError:
            return False

    def file_size(self, storage_key: str) -> int:
        return self.get_path(storage_key).stat().st_size

    def checksum(self, storage_key: str) -> str:
        path = self.get_path(storage_key)
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()


class S3StorageService(StorageService):
    """S3-compatible stub for future production use."""

    def save(self, category: str, filename: str, data: BinaryIO | bytes) -> str:
        raise AppError(ErrorCodes.STORAGE_ERROR, "S3 storage is not configured", status_code=501)

    def get_path(self, storage_key: str) -> Path:
        raise AppError(ErrorCodes.STORAGE_ERROR, "S3 storage is not configured", status_code=501)

    def delete(self, storage_key: str) -> None:
        raise AppError(ErrorCodes.STORAGE_ERROR, "S3 storage is not configured", status_code=501)

    def exists(self, storage_key: str) -> bool:
        return False

    def file_size(self, storage_key: str) -> int:
        raise AppError(ErrorCodes.STORAGE_ERROR, "S3 storage is not configured", status_code=501)


def get_storage() -> StorageService:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3StorageService()
    return LocalStorageService(settings)
