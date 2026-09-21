from pathlib import Path

import numpy as np

from app.detection.detector import ModelNotFoundError, load_yolo_model
from app.pipeline.geometry import BoundingBox, Detection


class PlateDetector:
    def __init__(
        self,
        model_path: str,
        device: str,
        confidence: float,
        iou: float,
        image_size: int,
        half: bool,
    ) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise ModelNotFoundError("plate_detector.pt", str(path))
        self.model = load_yolo_model(str(path), image_size, device, half and device.startswith("cuda"))
        self.device = device
        self.confidence = confidence
        self.iou = iou
        self.image_size = image_size
        self.half = half and device.startswith("cuda")

    def detect(
        self,
        image: np.ndarray,
        frame_number: int,
        timestamp: float,
        confidence: float | None = None,
        image_size: int | None = None,
    ) -> list[Detection]:
        batches = self.detect_many([image], frame_number, timestamp, confidence, image_size)
        return batches[0] if batches else []

    def detect_many(
        self,
        images: list[np.ndarray],
        frame_number: int,
        timestamp: float,
        confidence: float | None = None,
        image_size: int | None = None,
    ) -> list[list[Detection]]:
        if not images:
            return []
        results = self.model.predict(
            images,
            conf=self.confidence if confidence is None else confidence,
            iou=self.iou,
            imgsz=image_size or self.image_size,
            device=self.device,
            half=self.half,
            verbose=False,
        )
        batches: list[list[Detection]] = []
        for result in results:
            detections: list[Detection] = []
            if result.boxes is not None:
                for box in result.boxes:
                    xyxy = box.xyxy[0].tolist()
                    detections.append(
                        Detection(
                            bounding_box=BoundingBox(*xyxy),
                            class_name="license_plate",
                            confidence=float(box.conf[0]),
                            frame_number=frame_number,
                            timestamp=timestamp,
                        )
                    )
            batches.append(detections)
        return batches
