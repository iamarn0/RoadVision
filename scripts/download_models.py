"""Download documented model weights into models/.

Vehicle: Ultralytics YOLO11n (COCO) — detects car/motorcycle/bus/truck.
Plate: YOLOv8n fine-tuned on keremberke/license-plate-object-detection
       (Hugging Face: joker5914/yolov8n-license-plate).

Does not create empty placeholder .pt files.
"""

from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
MODELS.mkdir(parents=True, exist_ok=True)

# Public Ultralytics-compatible plate detector (YOLOv8n).
PLATE_URLS = (
    "https://huggingface.co/joker5914/yolov8n-license-plate/resolve/main/best.pt",
    "https://huggingface.co/joker5914/yolov8n-license-plate/resolve/main/best.pt?download=true",
)


def _download(url: str, dest: Path) -> None:
    print(f"Fetching {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "RoadVision/0.1"})
    with urllib.request.urlopen(req, timeout=120) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out)


def main() -> None:
    from ultralytics import YOLO

    vehicle_out = MODELS / "vehicle_detector.pt"
    if vehicle_out.exists() and vehicle_out.stat().st_size > 1_000_000:
        print(f"Vehicle model already present: {vehicle_out} ({vehicle_out.stat().st_size:,} bytes)")
    else:
        print("Downloading vehicle detector (yolo11n.pt from Ultralytics)...")
        YOLO("yolo11n.pt")
        source = None
        for candidate in (
            Path("yolo11n.pt"),
            ROOT / "yolo11n.pt",
            Path.home() / "AppData" / "Roaming" / "Ultralytics" / "yolo11n.pt",
        ):
            if candidate.exists() and candidate.stat().st_size > 1_000_000:
                source = candidate
                break
        if source is None:
            for path in Path.home().rglob("yolo11n.pt"):
                if path.stat().st_size > 1_000_000:
                    source = path
                    break
        if source is None:
            raise SystemExit("yolo11n.pt was not found after download")
        shutil.copy2(source, vehicle_out)
        print(f"Vehicle model: {vehicle_out} ({vehicle_out.stat().st_size:,} bytes)")

    plate_out = MODELS / "plate_detector.pt"
    print("Downloading plate detector (joker5914/yolov8n-license-plate)...")
    last_error: Exception | None = None
    for url in PLATE_URLS:
        try:
            _download(url, plate_out)
            if plate_out.stat().st_size > 1_000_000:
                break
            last_error = SystemExit("plate file too small")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            plate_out.unlink(missing_ok=True)
    else:
        raise SystemExit(f"Failed to download plate_detector.pt: {last_error}")

    # Validate it loads in Ultralytics
    YOLO(str(plate_out))
    print(f"Plate model: {plate_out} ({plate_out.stat().st_size:,} bytes)")

    cwd_weight = Path("yolo11n.pt")
    if cwd_weight.exists() and cwd_weight.resolve() != vehicle_out.resolve():
        cwd_weight.unlink(missing_ok=True)

    print("Done. Restart the Celery worker, then retry the job in the UI.")


if __name__ == "__main__":
    main()
