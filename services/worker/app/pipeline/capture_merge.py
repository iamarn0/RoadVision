from __future__ import annotations

from typing import Any

import numpy as np

from app.pipeline.geometry import BoundingBox

SAME_PASSAGE_WINDOW = 1.0
MIN_BOX_IOU = 0.25
MAX_PLATE_MEAN_DIFF = 18.0


def box_from_dict(data: dict[str, Any] | None) -> BoundingBox | None:
    if not data:
        return None
    try:
        return BoundingBox(float(data["x1"]), float(data["y1"]), float(data["x2"]), float(data["y2"]))
    except (KeyError, TypeError, ValueError):
        return None


def plate_crop_similar(image_a: Any, image_b: Any, max_mean_diff: float = MAX_PLATE_MEAN_DIFF) -> bool:
    import cv2

    if image_a is None or image_b is None:
        return False
    if getattr(image_a, "size", 0) == 0 or getattr(image_b, "size", 0) == 0:
        return False
    gray_a = cv2.cvtColor(image_a, cv2.COLOR_BGR2GRAY) if image_a.ndim == 3 else image_a
    gray_b = cv2.cvtColor(image_b, cv2.COLOR_BGR2GRAY) if image_b.ndim == 3 else image_b
    size = (64, 32)
    resized_a = cv2.resize(gray_a, size, interpolation=cv2.INTER_AREA)
    resized_b = cv2.resize(gray_b, size, interpolation=cv2.INTER_AREA)
    return float(cv2.absdiff(resized_a, resized_b).mean()) <= max_mean_diff


def find_same_passage(
    best_by_track: dict[int, dict[str, Any]],
    timestamp: float,
    vehicle_box: dict[str, float],
    plate_img: np.ndarray | None,
    exclude_track_id: int | None = None,
    window: float = SAME_PASSAGE_WINDOW,
) -> int | None:
    """Same overlay second + overlap or same plate crop → one vehicle, one row."""
    incoming = box_from_dict(vehicle_box)
    for track_id, capture in best_by_track.items():
        if exclude_track_id is not None and track_id == exclude_track_id:
            continue
        first = float(capture.get("first_seen") or 0.0)
        last = float(capture.get("last_seen") or first)
        if timestamp < first - window or timestamp > last + window:
            continue
        existing = box_from_dict(capture.get("vehicle_box"))
        iou = incoming.iou(existing) if incoming and existing else 0.0
        similar = plate_crop_similar(plate_img, capture.get("image_plate"))
        if iou >= MIN_BOX_IOU or similar:
            return track_id
    return None
