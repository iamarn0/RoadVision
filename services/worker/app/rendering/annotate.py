from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.pipeline.geometry import Detection
from app.tracking.tracker import TrackedVehicle


def draw_overlay(
    frame: np.ndarray,
    vehicles: list[TrackedVehicle],
    plates: list[tuple[TrackedVehicle, Detection]],
    captures: dict[int, dict[str, Any]] | None = None,
    timestamp: float = 0.0,
) -> np.ndarray:
    """Draw vehicle boxes and plate boxes. No OCR text is rendered."""
    canvas = frame.copy()
    captures = captures or {}
    cv2.putText(
        canvas,
        f"{timestamp:0.2f}s",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (220, 220, 220),
        2,
        cv2.LINE_AA,
    )
    for vehicle in vehicles:
        x1, y1, x2, y2 = vehicle.detection.bounding_box.as_int()
        has_plate = vehicle.track_id in captures
        color = (42, 180, 90) if has_plate else (47, 158, 158)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        label = f"{vehicle.detection.class_name.upper()} #{vehicle.track_id}"
        if has_plate:
            conf = captures[vehicle.track_id].get("plate_confidence")
            if conf is not None:
                label = f"{label} | PLATE {int(float(conf) * 100)}%"
        y = max(18, y1 - 8)
        cv2.putText(
            canvas,
            label,
            (x1, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (232, 237, 242),
            2,
            cv2.LINE_AA,
        )
    for vehicle, plate in plates:
        x1, y1, x2, y2 = plate.bounding_box.as_int()
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (201, 146, 42), 2)
        cv2.putText(
            canvas,
            "PLATE",
            (x1, max(18, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (201, 146, 42),
            2,
            cv2.LINE_AA,
        )
    return canvas


class AnnotatedVideoRenderer:
    def __init__(self, path: Path, fps: float, size: tuple[int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        width = max(2, int(size[0]) // 2 * 2)
        height = max(2, int(size[1]) // 2 * 2)
        self.path = path
        self._size = (width, height)
        self._writer = None
        for codec in ("mp4v", "XVID", "MJPG"):
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), max(float(fps), 1.0), self._size)
            if writer.isOpened():
                self._writer = writer
                break
            writer.release()
        if self._writer is None:
            raise RuntimeError(f"Could not open annotated video writer for {path}")

    def write(self, frame: np.ndarray) -> None:
        if self._writer is None:
            return
        if frame.shape[1] != self._size[0] or frame.shape[0] != self._size[1]:
            frame = cv2.resize(frame, self._size)
        self._writer.write(frame)

    def close(self) -> None:
        if self._writer is not None:
            self._writer.release()
            self._writer = None
