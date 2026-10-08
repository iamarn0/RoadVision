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

ROI_IMAGE_SIZE = 416
MIN_PLATE_SEARCH_AREA = 2500.0
MIN_PLATE_SEARCH_WIDTH = 36.0
WORKING_MAX_WIDTH = 960
# Share of the plate box that must sit on this vehicle. Stops a sharp plate
# in a neighbour's lane, caught only because of ROI padding, from being saved
# against the wrong car.
MIN_PLATE_INSIDE = 0.55


def make_working_image(image: np.ndarray) -> tuple[np.ndarray, float]:
    """Shrink a frame so detection does not run on native 4K pixels.

    Returns the working image and the scale that maps working pixels back to
    native pixels (native = working * scale).
    """
    import cv2

    height, width = image.shape[:2]
    if width <= WORKING_MAX_WIDTH:
        return image, 1.0
    new_w = WORKING_MAX_WIDTH
    new_h = max(2, int(round(height * (WORKING_MAX_WIDTH / float(width)))) // 2 * 2)
    new_w = max(2, new_w // 2 * 2)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    scale = float(width) / float(resized.shape[1])
    return resized, scale


def scale_detection(det: Detection, scale: float) -> Detection:
    if scale == 1.0:
        return det
    return Detection(
        bounding_box=det.bounding_box.scaled(scale, scale),
        class_name=det.class_name,
        confidence=det.confidence,
        frame_number=det.frame_number,
        timestamp=det.timestamp,
        track_id=det.track_id,
    )


def scale_vehicle(vehicle: TrackedVehicle, scale: float) -> TrackedVehicle:
    if scale == 1.0:
        return vehicle
    return TrackedVehicle(track_id=vehicle.track_id, detection=scale_detection(vehicle.detection, scale))


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
    """left, top, right, bottom — extra bottom pad for rear plates / motorcycles.

    Side pad stays small so the next car's plate is not inside this crop.
    """
    if class_name == "motorcycle":
        return 0.12, 0.08, 0.12, 0.28
    return 0.08, 0.06, 0.08, 0.20


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


def ownership_region(box: BoundingBox) -> BoundingBox:
    """Vehicle box plus a short bumper margin. Not the full search pad."""
    return BoundingBox(
        box.x1 - box.width * 0.06,
        box.y1 - box.height * 0.04,
        box.x2 + box.width * 0.06,
        box.y2 + box.height * 0.18,
    )


def _intersection_area(a: BoundingBox, b: BoundingBox) -> float:
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)


def plate_inside_fraction(plate: BoundingBox, vehicle: BoundingBox) -> float:
    area = plate.area
    if area <= 0:
        return 0.0
    return _intersection_area(plate, ownership_region(vehicle)) / area


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
    per_vehicle: dict[int, tuple[TrackedVehicle, Detection, float]] = {}
    for (ox, oy, vehicle), detections in zip(origins, batches):
        body = vehicle.detection.bounding_box
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
            inside = plate_inside_fraction(remapped.bounding_box, body)
            if inside < MIN_PLATE_INSIDE:
                continue
            current = per_vehicle.get(vehicle.track_id)
            if current is None or inside > current[2] or (
                abs(inside - current[2]) <= 0.05 and remapped.confidence > current[1].confidence
            ):
                per_vehicle[vehicle.track_id] = (vehicle, remapped, inside)
    ranked = sorted(per_vehicle.values(), key=lambda item: (item[2], item[1].confidence), reverse=True)
    assigned: list[tuple[TrackedVehicle, Detection]] = []
    kept_boxes: list[BoundingBox] = []
    for vehicle, plate, _inside in ranked:
        if any(plate.bounding_box.iou(prev) >= 0.35 for prev in kept_boxes):
            continue
        kept_boxes.append(plate.bounding_box)
        assigned.append((vehicle, plate))
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
