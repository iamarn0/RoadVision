from __future__ import annotations

from typing import Any

import numpy as np

from app.pipeline.geometry import BoundingBox

SAME_PASSAGE_WINDOW = 3.0
MIN_BOX_IOU = 0.45
MAX_PLATE_MEAN_DIFF = 28.0


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
        if incoming and existing and _centers_are_close(incoming, existing) and iou >= 0.12:
            return track_id
    return None


def _span(capture: dict[str, Any]) -> tuple[float, float]:
    start = float(capture.get("first_seen") or 0.0)
    end = float(capture.get("last_seen") or start)
    return start, max(start, end)


def time_gap(left: dict[str, Any], right: dict[str, Any]) -> float:
    a0, a1 = _span(left)
    b0, b1 = _span(right)
    if a1 < b0:
        return b0 - a1
    if b1 < a0:
        return a0 - b1
    return 0.0


def _centers_are_close(left: BoundingBox, right: BoundingBox) -> bool:
    ax, ay = left.center
    bx, by = right.center
    diag = max((left.width**2 + left.height**2) ** 0.5, (right.width**2 + right.height**2) ** 0.5, 1.0)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 <= diag * 0.35


def captures_are_same_passage(left: dict[str, Any], right: dict[str, Any], window: float = SAME_PASSAGE_WINDOW) -> bool:
    """One physical vehicle that the tracker split, or the same plate saved twice."""
    if time_gap(left, right) > window:
        return False
    box_a = box_from_dict(left.get("vehicle_box"))
    box_b = box_from_dict(right.get("vehicle_box"))
    iou = box_a.iou(box_b) if box_a and box_b else 0.0
    if iou >= MIN_BOX_IOU:
        return True
    if plate_crop_similar(left.get("image_plate"), right.get("image_plate")):
        return True
    if box_a and box_b and iou >= 0.12 and _centers_are_close(box_a, box_b):
        return True
    return False


def _has_plate(capture: dict[str, Any]) -> bool:
    plate = capture.get("image_plate")
    return plate is not None and getattr(plate, "size", 0) > 0 and not capture.get("vehicle_only")


def _absorb_capture(keeper: dict[str, Any], other: dict[str, Any], other_id: int) -> None:
    k0, k1 = _span(keeper)
    o0, o1 = _span(other)
    keeper["first_seen"] = min(k0, o0)
    keeper["last_seen"] = max(k1, o1)
    ids = set(keeper.get("source_ids") or [])
    ids.update(other.get("source_ids") or [])
    ids.add(other_id)
    keeper["source_ids"] = ids
    if other.get("active_tid") is not None:
        keeper["active_tid"] = other["active_tid"]
    take_images = _has_plate(other) and (not _has_plate(keeper) or float(other.get("quality") or 0) > float(keeper.get("quality") or 0))
    if take_images:
        for key in (
            "image_plate",
            "image_vehicle",
            "image_full",
            "quality",
            "score",
            "sharp",
            "plate_area",
            "contrast",
            "brightness",
            "plate_width",
            "plate_height",
            "good_evidence",
            "best_frame",
            "plate_confidence",
            "vehicle_confidence",
            "vehicle_type",
            "plate_box",
            "vehicle_box",
            "observation",
        ):
            if key in other:
                keeper[key] = other[key]
        keeper["vehicle_only"] = False
    elif not keeper.get("vehicle_box") and other.get("vehicle_box"):
        keeper["vehicle_box"] = other["vehicle_box"]
    keeper_vehicle = keeper.get("image_vehicle")
    other_vehicle = other.get("image_vehicle")
    keeper_missing = keeper_vehicle is None or getattr(keeper_vehicle, "size", 0) == 0
    if keeper_missing and other_vehicle is not None and getattr(other_vehicle, "size", 0) > 0:
        keeper["image_vehicle"] = other_vehicle
    if keeper.get("published") or other.get("published"):
        keeper["published"] = True


def collapse_duplicate_captures(best_by_track: dict[int, dict[str, Any]]) -> list[tuple[int, int]]:
    """Fold split track ids for the same pass into one row. Returns (keep, drop) pairs."""
    merged: list[tuple[int, int]] = []
    changed = True
    while changed:
        changed = False
        ids = list(best_by_track)
        for index, left_id in enumerate(ids):
            if left_id not in best_by_track:
                continue
            for right_id in ids[index + 1 :]:
                if right_id not in best_by_track:
                    continue
                left = best_by_track[left_id]
                right = best_by_track[right_id]
                if not captures_are_same_passage(left, right):
                    continue
                keep_id, drop_id = _keeper_id(left_id, left, right_id, right)
                _absorb_capture(best_by_track[keep_id], best_by_track[drop_id], drop_id)
                del best_by_track[drop_id]
                merged.append((keep_id, drop_id))
                changed = True
                break
            if changed:
                break
    return merged


def _keeper_id(
    left_id: int,
    left: dict[str, Any],
    right_id: int,
    right: dict[str, Any],
) -> tuple[int, int]:
    if bool(left.get("published")) != bool(right.get("published")):
        return (left_id, right_id) if left.get("published") else (right_id, left_id)
    if _has_plate(left) != _has_plate(right):
        return (left_id, right_id) if _has_plate(left) else (right_id, left_id)
    if float(left.get("quality") or 0) != float(right.get("quality") or 0):
        return (left_id, right_id) if float(left.get("quality") or 0) >= float(right.get("quality") or 0) else (right_id, left_id)
    return (left_id, right_id) if left_id <= right_id else (right_id, left_id)
