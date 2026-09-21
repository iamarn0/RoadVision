import logging
import threading
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from app.pipeline.geometry import BoundingBox, Detection

logger = logging.getLogger("worker")

_YOLO_CACHE: dict[str, Any] = {}
_YOLO_WARMED: set[str] = set()
_YOLO_LOCK = threading.Lock()


def load_yolo_model(model_path: str, image_size: int, device: str, half: bool) -> Any:
    """Reuse YOLO weights in-process so later jobs skip disk/CUDA reload."""
    from ultralytics import YOLO

    key = str(Path(model_path).resolve())
    with _YOLO_LOCK:
        cached = _YOLO_CACHE.get(key)
        if cached is None:
            logger.info("loading YOLO weights %s", key)
            cached = YOLO(key)
            _YOLO_CACHE[key] = cached
        else:
            logger.info("reusing cached YOLO weights %s", key)
        if key not in _YOLO_WARMED:
            dummy = np.zeros((max(int(image_size), 32), max(int(image_size), 32), 3), dtype=np.uint8)
            try:
                cached.predict(dummy, imgsz=image_size, device=device, half=half, verbose=False)
            except Exception:
                logger.debug("yolo warmup skipped", exc_info=True)
            _YOLO_WARMED.add(key)
        return cached


VEHICLE_CLASS_MAP = {
    "car": "car",
    "motorcycle": "motorcycle",
    "motorbike": "motorcycle",
    "bus": "bus",
    "truck": "truck",
    "van": "van",
    "automobile": "car",
}


class ModelNotFoundError(Exception):
    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path = path
        super().__init__(f"Required model: {name}\nExpected location:\n{path}")


class VehicleDetector:
    def __init__(
        self,
        model_path: str,
        device: str,
        confidence: float,
        iou: float,
        image_size: int,
        half: bool,
        allowed: Sequence[str] | None = None,
    ) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise ModelNotFoundError("vehicle_detector.pt", str(path))
        self.model = load_yolo_model(str(path), image_size, device, half and device.startswith("cuda"))
        self.device = device
        self.confidence = confidence
        self.iou = iou
        self.image_size = image_size
        self.half = half and device.startswith("cuda")
        self.allowed = set(allowed or VEHICLE_CLASS_MAP.keys())
        self.reset_tracking()

    def reset_tracking(self) -> None:
        """Clear ByteTrack state so a cached model does not leak IDs across jobs."""
        predictor = getattr(self.model, "predictor", None)
        if predictor is None:
            return
        if hasattr(predictor, "trackers"):
            predictor.trackers = []
        vid_path = getattr(predictor, "vid_path", None)
        if isinstance(vid_path, list):
            predictor.vid_path = [None] * len(vid_path)

    def detect(self, image: np.ndarray, frame_number: int, timestamp: float) -> list[Detection]:
        results = self.model.predict(
            image,
            conf=self.confidence,
            iou=self.iou,
            imgsz=self.image_size,
            device=self.device,
            half=self.half,
            verbose=False,
        )
        detections: list[Detection] = []
        for result in results:
            names = result.names
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                raw_name = str(names.get(cls_id, cls_id)).lower()
                mapped = VEHICLE_CLASS_MAP.get(raw_name)
                if mapped is None or raw_name not in self.allowed and mapped not in self.allowed:
                    if mapped is None:
                        continue
                xyxy = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        bounding_box=BoundingBox(*xyxy),
                        class_name=mapped or raw_name,
                        confidence=float(box.conf[0]),
                        frame_number=frame_number,
                        timestamp=timestamp,
                    )
                )
        return detections
