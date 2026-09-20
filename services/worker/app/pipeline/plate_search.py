from __future__ import annotations

from typing import Any

import numpy as np

from app.pipeline.geometry import BoundingBox, Detection
from app.preprocessing.plates import (
    HIGH_EVIDENCE_SCORE,
    ROI_ENHANCE_LUMINANCE_MAX,
    crop_box_asymmetric,
    enhance_low_light_frame,
    frame_luminance,
)
from app.tracking.tracker import TrackedVehicle

ROI_IMAGE_SIZE = 320
MIN_PLATE_SEARCH_AREA = 2500.0
MIN_PLATE_SEARCH_WIDTH = 36.0


def remap_plate_box(local: BoundingBox, origin_x: float, origin_y: float) -> BoundingBox:
    return BoundingBox(
        local.x1 + origin_x,
        local.y1 + origin_y,
        local.x2 + origin_x,
        local.y2 + origin_y,
    )


def vehicle_roi_pads(class_name: str) -> tuple[float, float, float, float]:
    """left, top, right, bottom — extra bottom pad for rear plates / motorcycles."""
    if class_name == "motorcycle":
        return 0.28, 0.12, 0.28, 0.42
    return 0.22, 0.12, 0.22, 0.32


def crop_vehicle_roi(
    image: np.ndarray,
    box: BoundingBox,
    class_name: str,
) -> tuple[np.ndarray, int, int]:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = box.clip(w, h).as_int()
    pad_l, pad_t, pad_r, pad_b = vehicle_roi_pads(class_name)
    return crop_box_asymmetric(image, x1, y1, x2, y2, pad_l, pad_t, pad_r, pad_b)


def prepare_roi_for_detect(roi: np.ndarray) -> np.ndarray:
    if roi.size == 0:
        return roi
    if frame_luminance(roi) < ROI_ENHANCE_LUMINANCE_MAX:
        return enhance_low_light_frame(roi)
    return roi


def skip_ids_with_strong_evidence(
    vehicles: list[TrackedVehicle],
    best_by_track: dict[int, dict[str, Any]],
    previous_areas: dict[int, float],
    high_score: float = HIGH_EVIDENCE_SCORE,
) -> set[int]:
    skip: set[int] = set()
    for vehicle in vehicles:
        best = best_by_track.get(vehicle.track_id)
        if not best or float(best.get("score") or 0.0) < high_score:
            continue
        area = vehicle.detection.bounding_box.area
        prev = previous_areas.get(vehicle.track_id, 0.0)
        grew = prev > 0 and area > prev * 1.18
        if not grew:
            skip.add(vehicle.track_id)
    return skip


def search_plates_in_vehicles(
    frame_image: np.ndarray,
    vehicles: list[TrackedVehicle],
    detector: Any,
    frame_number: int,
    timestamp: float,
    skip_ids: set[int] | None = None,
    confidence: float | None = None,
) -> list[tuple[TrackedVehicle, Detection]]:
    """Run plate YOLO on padded vehicle ROIs and remap boxes to frame coordinates."""
    skip_ids = skip_ids or set()
    rois: list[np.ndarray] = []
    origins: list[tuple[int, int, TrackedVehicle]] = []
    for vehicle in vehicles:
        if vehicle.track_id in skip_ids:
            continue
        box = vehicle.detection.bounding_box
        if box.area < MIN_PLATE_SEARCH_AREA or box.width < MIN_PLATE_SEARCH_WIDTH:
            continue
        roi, ox, oy = crop_vehicle_roi(frame_image, box, vehicle.detection.class_name)
        if roi.size == 0 or roi.shape[0] < 12 or roi.shape[1] < 12:
            continue
        rois.append(prepare_roi_for_detect(roi))
        origins.append((ox, oy, vehicle))
    if not rois:
        return []

    batches = detector.detect_many(
        rois,
        frame_number,
        timestamp,
        confidence=confidence,
        image_size=ROI_IMAGE_SIZE,
    )
    assigned: list[tuple[TrackedVehicle, Detection]] = []
    for (ox, oy, vehicle), detections in zip(origins, batches):
        best: Detection | None = None
        for det in detections:
            remapped = Detection(
                bounding_box=remap_plate_box(det.bounding_box, ox, oy),
                class_name=det.class_name,
                confidence=det.confidence,
                frame_number=frame_number,
                timestamp=timestamp,
                track_id=vehicle.track_id,
            )
            if best is None or remapped.confidence > best.confidence:
                best = remapped
        if best:
            assigned.append((vehicle, best))
    return assigned
