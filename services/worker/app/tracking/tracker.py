import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.pipeline.geometry import Detection

logger = logging.getLogger("worker")

# Stock ByteTrack will not open a track below 0.25. Departing trucks at night sit under that.
TRACKER_CONFIG = Path(__file__).with_name("bytetrack_cctv.yaml")


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
                tracked: list[TrackedVehicle] = []
                from app.detection.detector import VEHICLE_CLASS_MAP
                from app.pipeline.geometry import BoundingBox, Detection

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
                        track_id = int(ids[i]) if ids is not None else self._next_id
                        if ids is None:
                            self._next_id += 1
                        det = Detection(
                            bounding_box=BoundingBox(*box.xyxy[0].tolist()),
                            class_name=mapped,
                            confidence=float(box.conf[0]),
                            frame_number=frame_number,
                            timestamp=timestamp,
                            track_id=track_id,
                        )
                        tracked.append(TrackedVehicle(track_id=track_id, detection=det))
                self._previous = tracked
                return tracked
            except Exception:
                logger.exception("ByteTrack update failed; falling back to IoU association")
        detections = self.detector.detect(image, frame_number, timestamp, confidence=conf)
        return self._iou_associate(detections)

    def _iou_associate(self, detections: list[Detection]) -> list[TrackedVehicle]:
        assigned: list[TrackedVehicle] = []
        used_prev: set[int] = set()
        for det in sorted(detections, key=lambda d: d.confidence, reverse=True):
            best_id = None
            best_iou = 0.3
            for prev in self._previous:
                if prev.track_id in used_prev:
                    continue
                iou = det.bounding_box.iou(prev.detection.bounding_box)
                if iou > best_iou:
                    best_iou = iou
                    best_id = prev.track_id
            if best_id is None:
                best_id = self._next_id
                self._next_id += 1
            used_prev.add(best_id)
            det.track_id = best_id
            assigned.append(TrackedVehicle(track_id=best_id, detection=det))
        self._previous = assigned
        return assigned
