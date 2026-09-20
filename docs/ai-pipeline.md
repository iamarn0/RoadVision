# AI pipeline

The worker owns all computer vision. The API never runs detectors.

## Principles

- Real inference only
- Stream frames; never load an entire video into RAM
- Track vehicles; do not create one vehicle row per frame
- Dedicated plate detector
- OCR is interval-gated and quality-gated
- Store raw OCR and normalized text separately
- Aggregate over time; suppress duplicates for the operator UI
- Fail with `MODEL_NOT_FOUND` / `CUDA_UNAVAILABLE` / `CUDA_OUT_OF_MEMORY` instead of inventing results

## Modules

| Module | Interface role |
| --- | --- |
| `VideoSource` / `UploadedFileSource` | Open, read, close, metadata |
| `VehicleDetector` | Boxes, class, confidence |
| `VehicleTracker` | ByteTrack or BoT-SORT track IDs |
| `PlateDetector` | Plate boxes inside or near vehicles |
| Association | Spatial assignment of plate → track |
| `PlatePreprocessor` | Conservative crop/enhance |
| `OCREngine` | `read(image) -> OCRResult` |
| `PlateNormalizer` | Conservative Indian plate cleanup |
| `ObservationAggregator` | Frequency, confidence, edit distance |
| `DuplicateSuppressor` | Unique detections |
| `EvidenceGenerator` | Best-frame full / vehicle / plate crops |
| `AnnotatedVideoRenderer` | Overlay boxes and labels |

## Video source abstraction

Current implementation target: `UploadedFileSource`.

Reserved for later (not implemented in v0.1.0): `RTSPSource`, `WebcamSource`, `IPCameraSource`.

Pipeline code should depend on `VideoSource`, not on filesystem upload details.

## Performance profile

| Profile | Image size | Frame skip | OCR interval | FP16 on CUDA |
| --- | --- | --- | --- | --- |
| Balanced | 640 | 0 | 3 | yes |
| Performance | 512 | 1 | 5 | yes |
| Accuracy | 960 | 0 | 1 | configurable |
| Custom | from settings | | | |

These are quality/speed trade-offs, not real-time guarantees. UI shows measured FPS.

## GPU memory

On CUDA OOM: log, free caches, mark job `CUDA_OUT_OF_MEMORY`, suggest Performance profile or lower `INFERENCE_IMAGE_SIZE`. Optional `AUTO_FALLBACK_TO_CPU` must be visible in logs and UI.

## Confidence states

Configurable thresholds (`HIGH_CONFIDENCE_THRESHOLD`, `MEDIUM_CONFIDENCE_THRESHOLD`, `LOW_CONFIDENCE_THRESHOLD`):

- High Confidence
- Medium Confidence
- Low Confidence
- Uncertain
- Needs Verification

These are operational labels, not accuracy SLAs.
