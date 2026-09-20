# Model management

RoadVision does **not** commit model weights. Dummy `.pt` files are forbidden. The worker fails with `MODEL_NOT_FOUND` if required files are absent.

## Required models

| Role | Environment variable | Default path | Expected format |
| --- | --- | --- | --- |
| Vehicle detector | `VEHICLE_MODEL_PATH` | `models/vehicle_detector.pt` | Ultralytics YOLO `.pt` detecting vehicle classes |
| Plate detector | `PLATE_MODEL_PATH` | `models/plate_detector.pt` | Ultralytics YOLO `.pt` dedicated to license plates |

OCR (EasyOCR by default) downloads its own recognition weights on first use unless you pin a local cache. That is separate from these two detectors.

## Vehicle detector

Must emit classes that can be mapped to:

- car
- motorcycle
- bus
- truck
- van

## Recommended vehicle checkpoint (document source/license)

Ultralytics YOLO models are commonly used for COCO vehicle classes:

1. Download a nano/small YOLO weight you are licensed to use (for example `yolo11n.pt` from Ultralytics).
2. Copy or symlink it to `models/vehicle_detector.pt`.
3. Set `VEHICLE_MODEL_VERSION` to the checkpoint name and date.

Example (operator-run; not performed automatically by RoadVision):

```bash
# After installing ultralytics in the worker environment:
python -c "from ultralytics import YOLO; YOLO('yolo11n.pt').save('models/vehicle_detector.pt')"
```

Always review Ultralytics license terms before redistribution.

## Plate detector

Do **not** treat vehicle boxes as plates. Use a dedicated license-plate detector.

Recommended public checkpoint for demos:

- Source: [joker5914/yolov8n-license-plate](https://huggingface.co/joker5914/yolov8n-license-plate)
- Trained on: [keremberke/license-plate-object-detection](https://huggingface.co/datasets/keremberke/license-plate-object-detection)
- Local path: `models/plate_detector.pt`

Download both detectors:

```powershell
py -3 scripts\download_models.py
```

If missing, processing stops with `MODEL_NOT_FOUND`. The UI shows the expected path; detections are never fabricated.

## Setup process

1. Obtain licensed weights you are allowed to use.
2. Copy them into `models/` with the names above, or set explicit paths in `.env`.
3. Set `VEHICLE_MODEL_VERSION` and `PLATE_MODEL_VERSION` so each job stores reproducibility metadata.
4. Restart the worker. Confirm `/api/system/health` reports models as present.

## License considerations

You are responsible for complying with:

- Ultralytics / YOLO license terms for the checkpoint you use
- Dataset licenses if you train a plate detector
- EasyOCR / PaddleOCR model licenses
- Local law for collecting and storing vehicle registration data

RoadVision does not redistribute third-party weights.

## What not to do

- Do not commit large binaries
- Do not download unverified random checkpoints in CI
- Do not create empty placeholder `.pt` files to “make the UI look ready”
