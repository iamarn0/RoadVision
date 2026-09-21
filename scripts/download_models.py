"""Download documented model weights into models/.

Vehicle: Ultralytics YOLO26n (COCO) — detects car/motorcycle/bus/truck.
Plate: YOLO26n fine-tuned for license plates
       (Hugging Face: CodexParas/car-plate-detection-yolov26).

Does not create empty placeholder .pt files.
"""

from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
MODELS.mkdir(parents=True, exist_ok=True)

# Latest released Ultralytics COCO detector. YOLO27 weights are not published yet.
VEHICLE_WEIGHT = "yolo26n.pt"

# Public Ultralytics YOLO26n license-plate detector.
PLATE_URLS = (
    "https://huggingface.co/CodexParas/car-plate-detection-yolov26/resolve/main/best.pt",
    "https://huggingface.co/CodexParas/car-plate-detection-yolov26/resolve/main/best.pt?download=true",
)


def _download(url: str, dest: Path) -> None:
    print(f"Fetching {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "RoadVision/0.1"})
    with urllib.request.urlopen(req, timeout=120) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out)


def _is_yolo26(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 1_000_000:
        return False
    import torch

    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    train_args = checkpoint.get("train_args") or {}
    model_name = Path(str(train_args.get("model") or "")).name.lower()
    return model_name.startswith("yolo26")


def main() -> None:
    from ultralytics import YOLO

    vehicle_out = MODELS / "vehicle_detector.pt"
    if _is_yolo26(vehicle_out):
        print(f"Vehicle model already present: {vehicle_out} ({vehicle_out.stat().st_size:,} bytes)")
    else:
        print(f"Downloading vehicle detector ({VEHICLE_WEIGHT} from Ultralytics)...")
        model = YOLO(VEHICLE_WEIGHT)
        source = Path(str(getattr(model, "ckpt_path", "") or ""))
        if not source.is_file() or source.stat().st_size <= 1_000_000:
            source = Path()
            for candidate in (
                Path(VEHICLE_WEIGHT),
                ROOT / VEHICLE_WEIGHT,
                Path.home() / "AppData" / "Roaming" / "Ultralytics" / VEHICLE_WEIGHT,
            ):
                if candidate.is_file() and candidate.stat().st_size > 1_000_000:
                    source = candidate
                    break
        if not source.is_file():
            raise SystemExit(f"{VEHICLE_WEIGHT} was not found after download")
        shutil.copy2(source, vehicle_out)
        print(f"Vehicle model: {vehicle_out} ({vehicle_out.stat().st_size:,} bytes)")

    plate_out = MODELS / "plate_detector.pt"
    if _is_yolo26(plate_out):
        print(f"Plate model already present: {plate_out} ({plate_out.stat().st_size:,} bytes)")
    else:
        print("Downloading plate detector (CodexParas/car-plate-detection-yolov26)...")
        last_error: Exception | None = None
        for url in PLATE_URLS:
            try:
                _download(url, plate_out)
                if plate_out.stat().st_size > 1_000_000 and _is_yolo26(plate_out):
                    break
                last_error = SystemExit("plate file is missing or is not a YOLO26 checkpoint")
                plate_out.unlink(missing_ok=True)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                plate_out.unlink(missing_ok=True)
        else:
            raise SystemExit(f"Failed to download plate_detector.pt: {last_error}")

        YOLO(str(plate_out))
        print(f"Plate model: {plate_out} ({plate_out.stat().st_size:,} bytes)")

    cwd_weight = Path(VEHICLE_WEIGHT)
    if cwd_weight.exists() and cwd_weight.resolve() != vehicle_out.resolve():
        cwd_weight.unlink(missing_ok=True)

    print("Done. Restart the Celery worker, then retry the job in the UI.")


if __name__ == "__main__":
    main()
