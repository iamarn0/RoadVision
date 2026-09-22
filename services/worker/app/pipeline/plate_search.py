from __future__ import annotations

from typing import Any

import numpy as np

from app.pipeline.geometry import BoundingBox, Detection
from app.preprocessing.plates import (
    ROI_ENHANCE_LUMINANCE_MAX,
    VEHICLE_CROP_PAD,
    crop_box_asymmetric,
    enhance_low_light_frame,
    frame_luminance,
    is_burned_in_caption,
)
from app.tracking.tracker import TrackedVehicle

ROI_IMAGE_SIZE = 960
MIN_PLATE_SEARCH_AREA = 2500.0
MIN_PLATE_SEARCH_WIDTH = 36.0


def remap_plate_box(local: BoundingBox, origin_x: float, origin_y: float) -> BoundingBox:
    return local.translated(origin_x, origin_y)


def map_resized_box_to_original(
    local: BoundingBox,
    resized_width: float,
    resized_height: float,
    native_width: float,
    native_height: float,
    origin_x: float = 0.0,
    origin_y: float = 0.0,
) -> BoundingBox:
    """Map a box from a resized detection copy back onto the original frame.

    YOLO may run on a smaller copy. The crop for saving is always taken from
    native-resolution pixels after this mapping.
    """
    scale_x = float(native_width) / max(float(resized_width), 1.0)
    scale_y = float(native_height) / max(float(resized_height), 1.0)
    return local.scaled(scale_x, scale_y).translated(origin_x, origin_y)


def crop_from_original(
    original: Any,
    box: BoundingBox,
    pad: float = 0.0,
) -> Any:
    from app.preprocessing.plates import crop_box

    h, w = original.shape[:2]
    x1, y1, x2, y2 = box.clip(w, h).as_int()
    return crop_box(original, x1, y1, x2, y2, pad=pad)


def vehicle_roi_pads(class_name: str) -> tuple[float, float, float, float]:
    """left, top, right, bottom — extra bottom pad for rear plates / motorcycles."""
    if class_name == "motorcycle":
        return 0.28, 0.12, 0.28, 0.42
    return 0.22, 0.12, 0.22, 0.32


def vehicle_capture_pads(class_name: str) -> tuple[float, float, float, float]:
    """Saved vehicle crop: context around the body plus extra bumper/plate at the bottom."""
    if class_name == "motorcycle":
        return VEHICLE_CROP_PAD, 0.10, VEHICLE_CROP_PAD, 0.38
    return VEHICLE_CROP_PAD, 0.10, VEHICLE_CROP_PAD, 0.28


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


def search_plates_in_vehicles(
    frame_image: np.ndarray,
    vehicles: list[TrackedVehicle],
    detector: Any,
    frame_number: int,
    timestamp: float,
    skip_ids: set[int] | None = None,
    confidence: float | None = None,
    image_size: int | None = None,
) -> list[tuple[TrackedVehicle, Detection]]:
    """Run plate YOLO on padded vehicle ROIs and remap boxes to frame coordinates.

    The ROI is a native-resolution crop of the original frame. Detector `imgsz`
    only affects the internal letterbox. Returned boxes are in ROI pixels and
    then shifted by the crop origin so the final plate cut uses original pixels.
    """
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
        image_size=image_size or ROI_IMAGE_SIZE,
    )
    frame_h, frame_w = frame_image.shape[:2]
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
            if _crop_is_caption(frame_image, remapped, frame_w, frame_h):
                continue
            if best is None or remapped.confidence > best.confidence:
                best = remapped
        if best:
            assigned.append((vehicle, best))
    return assigned


def _crop_is_caption(frame: np.ndarray, plate: Detection, frame_w: int, frame_h: int) -> bool:
    x1, y1, x2, y2 = plate.bounding_box.clip(frame_w, frame_h).as_int()
    if x2 <= x1 or y2 <= y1:
        return False
    return is_burned_in_caption(frame[y1:y2, x1:x2])


def drop_caption_plates(frame: np.ndarray, plates: list[Detection]) -> list[Detection]:
    """Drop plate boxes that sit on the burned-in camera caption."""
    if frame.size == 0:
        return plates
    frame_h, frame_w = frame.shape[:2]
    return [plate for plate in plates if not _crop_is_caption(frame, plate, frame_w, frame_h)]
