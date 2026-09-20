from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.config import Settings, get_settings
from app.core.errors import AppError, ErrorCodes


def probe_video_metadata(path: Path) -> dict[str, Any]:
    try:
        import cv2
    except Exception as exc:  # pragma: no cover
        raise AppError(
            ErrorCodes.VIDEO_INVALID,
            "OpenCV is required to validate video files.",
            status_code=500,
            details={"reason": str(exc)},
        ) from exc

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise AppError(ErrorCodes.VIDEO_CORRUPTED, "The uploaded file could not be opened as a video.")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fourcc = int(capture.get(cv2.CAP_PROP_FOURCC) or 0)
        codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]).strip() or None
        ok, frame = capture.read()
        if not ok or frame is None:
            raise AppError(ErrorCodes.VIDEO_CORRUPTED, "The video could not be decoded (no readable frames).")
        duration = (frame_count / fps) if fps > 0 else None
        if width <= 0 or height <= 0:
            raise AppError(ErrorCodes.VIDEO_INVALID, "Video resolution is invalid.")
        return {
            "width": width,
            "height": height,
            "fps": fps if fps > 0 else None,
            "frame_count": frame_count if frame_count > 0 else None,
            "codec": codec,
            "duration": duration,
        }
    finally:
        capture.release()


def validate_upload(
    filename: str,
    content_type: Optional[str],
    size: int,
    settings: Optional[Settings] = None,
) -> str:
    settings = settings or get_settings()
    if size <= 0:
        raise AppError(ErrorCodes.VIDEO_INVALID, "Empty files are not accepted.")
    if size > settings.max_upload_bytes:
        raise AppError(
            ErrorCodes.VIDEO_UNSUPPORTED,
            f"File exceeds the maximum size of {settings.max_upload_bytes} bytes.",
        )
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in settings.allowed_extensions_set:
        raise AppError(
            ErrorCodes.VIDEO_UNSUPPORTED,
            f"Extension .{suffix} is not allowed.",
            details={"allowed": sorted(settings.allowed_extensions_set)},
        )
    if content_type:
        mime = content_type.split(";")[0].strip().lower()
        if mime not in settings.allowed_mime_set and mime != "application/octet-stream":
            raise AppError(
                ErrorCodes.VIDEO_UNSUPPORTED,
                f"MIME type {mime} is not allowed.",
                details={"allowed": sorted(settings.allowed_mime_set)},
            )
    return suffix
