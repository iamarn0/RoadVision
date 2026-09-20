from pathlib import Path
from typing import Sequence

import numpy as np

from app.pipeline.geometry import BoundingBox, Detection

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
        from ultralytics import YOLO

        self.model = YOLO(str(path))
        self.device = device
        self.confidence = confidence
        self.iou = iou
        self.image_size = image_size
        self.half = half and device.startswith("cuda")
        self.allowed = set(allowed or VEHICLE_CLASS_MAP.keys())

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
