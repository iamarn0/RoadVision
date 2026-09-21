from pathlib import Path
from uuid import uuid4

import numpy as np

from app.aggregation.temporal import UniqueDetection
from app.preprocessing.plates import JPEG_EVIDENCE_QUALITY, JPEG_PLATE_QUALITY, save_jpeg as write_jpeg


def save_jpeg(path: Path, image: np.ndarray, quality: int = JPEG_EVIDENCE_QUALITY) -> None:
    write_jpeg(path, image, quality)


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
        quality = JPEG_PLATE_QUALITY if name == "plate_crop" else JPEG_EVIDENCE_QUALITY
        save_jpeg(folder / filename, image, quality)
        keys[name] = f"evidence/{job_id}/track_{detection.track_id}/{filename}"
    return keys
