from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from app.aggregation.temporal import UniqueDetection


def save_jpeg(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)


def write_evidence(root: Path, job_id: str, detection: UniqueDetection) -> dict[str, str]:
    best = detection.best
    if best is None:
        return {}
    folder = root / "evidence" / job_id / f"track_{detection.track_id}"
    keys = {}
    mapping = {
        "full_frame": best.image_full,
        "vehicle_crop": best.image_vehicle,
        "plate_crop": best.image_plate,
    }
    for name, image in mapping.items():
        if image is None or getattr(image, "size", 0) == 0:
            continue
        filename = f"{name}_{uuid4().hex}.jpg"
        save_jpeg(folder / filename, image)
        keys[name] = f"evidence/{job_id}/track_{detection.track_id}/{filename}"
    return keys
