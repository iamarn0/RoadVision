import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.pipeline.geometry import BoundingBox, Detection

logger = logging.getLogger("worker")

# Stock ByteTrack will not open a track below 0.25. Departing trucks at night sit under that.
TRACKER_CONFIG = Path(__file__).with_name("bytetrack_cctv.yaml")
IOU_MATCH_MIN = 0.3


def coerce_track_id(value: object) -> int | None:
    """Return a usable ByteTrack id, or None for missing/NaN/unconfirmed detections.

    Ultralytics leaves `boxes.id` as None on the first look, and individual ids as
    NaN until a track is confirmed. `int(nan)` raises and used to abort the whole
    ByteTrack update, minting a fresh IoU id for every box on that frame.
    """
    if value is None:
        return None
    if hasattr(value, "detach"):
        try:
            value = value.detach()
        except Exception:
            pass
    if hasattr(value, "cpu"):
        try:
            value = value.cpu()
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    track_id = int(number)
    return track_id if track_id >= 0 else None


@dataclass
class TrackedVehicle:
    track_id: int
    detection: Detection


class VehicleTracker:
    """ByteTrack via Ultralytics. Falls back to a simple IoU tracker if track() is unavailable."""

    def __init__(self, detector, persist: bool = True) -> None:
        self.detector = detector
        self.persist = persist
        self._next_id = 1
        self._previous: list[TrackedVehicle] = []

    def _note_id(self, track_id: int) -> None:
        if track_id >= self._next_id:
            self._next_id = track_id + 1

    def update(
        self,
        image: np.ndarray,
        frame_number: int,
        timestamp: float,
        confidence: float | None = None,
    ) -> list[TrackedVehicle]:
        conf = self.detector.confidence if confidence is None else confidence
        model = getattr(self.detector, "model", None)
        if model is not None and hasattr(model, "track"):
            try:
                results = model.track(
                    image,
                    persist=self.persist,
                    conf=conf,
                    iou=self.detector.iou,
                    imgsz=self.detector.image_size,
                    device=self.detector.device,
                    half=self.detector.half,
                    tracker=str(TRACKER_CONFIG),
                    verbose=False,
                )
                tracked, unidentified = self._vehicles_from_track_results(
                    results, frame_number, timestamp
                )
                if unidentified:
                    reserved = {item.track_id for item in tracked}
                    # When ByteTrack emitted no ids (first frame or persist reset),
                    # IoU against the previous frame keeps the same physical vehicles.
                    # Unconfirmed boxes mixed into a live ByteTrack result must not
                    # mint ids — the tracker will confirm them on a later frame.
                    tracked.extend(
                        self._iou_associate(
                            unidentified,
                            reserved=reserved,
                            replace_previous=False,
                            allow_new=not tracked,
                        )
                    )
                self._previous = tracked
                return tracked
            except Exception:
                logger.exception("ByteTrack update failed; falling back to IoU association")
        detections = self.detector.detect(image, frame_number, timestamp, confidence=conf)
        return self._iou_associate(detections)

    def _vehicles_from_track_results(
        self,
        results,
        frame_number: int,
        timestamp: float,
    ) -> tuple[list[TrackedVehicle], list[Detection]]:
        from app.detection.detector import VEHICLE_CLASS_MAP

        tracked: list[TrackedVehicle] = []
        unidentified: list[Detection] = []
        for result in results:
            names = result.names
            if result.boxes is None:
                continue
            ids = result.boxes.id
            for i, box in enumerate(result.boxes):
                cls_id = int(box.cls[0])
                raw_name = str(names.get(cls_id, cls_id)).lower()
                mapped = VEHICLE_CLASS_MAP.get(raw_name)
                if mapped is None:
                    continue
                xyxy = box.xyxy[0]
                coords = xyxy.tolist() if hasattr(xyxy, "tolist") else list(xyxy)
                det = Detection(
                    bounding_box=BoundingBox(*coords),
                    class_name=mapped,
                    confidence=float(box.conf[0]),
                    frame_number=frame_number,
                    timestamp=timestamp,
                )
                track_id = None
                if ids is not None:
                    try:
                        track_id = coerce_track_id(ids[i])
                    except Exception:
                        track_id = None
                if track_id is None:
                    unidentified.append(det)
                    continue
                self._note_id(track_id)
                det.track_id = track_id
                tracked.append(TrackedVehicle(track_id=track_id, detection=det))
        return tracked, unidentified

    def _iou_associate(
        self,
        detections: list[Detection],
        reserved: set[int] | None = None,
        replace_previous: bool = True,
        allow_new: bool = True,
    ) -> list[TrackedVehicle]:
        assigned: list[TrackedVehicle] = []
        used_prev: set[int] = set(reserved or ())
        for det in sorted(detections, key=lambda item: item.confidence, reverse=True):
            best_id = None
            best_iou = IOU_MATCH_MIN
            for prev in self._previous:
                if prev.track_id in used_prev:
                    continue
                iou = det.bounding_box.iou(prev.detection.bounding_box)
                if iou > best_iou:
                    best_iou = iou
                    best_id = prev.track_id
            if best_id is None:
                if not allow_new:
                    continue
                best_id = self._next_id
                self._next_id += 1
            else:
                self._note_id(best_id)
            used_prev.add(best_id)
            det.track_id = best_id
            assigned.append(TrackedVehicle(track_id=best_id, detection=det))
        if replace_previous:
            self._previous = assigned
        return assigned
