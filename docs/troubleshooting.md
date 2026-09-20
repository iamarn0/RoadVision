# Troubleshooting

## CUDA unavailable

Symptoms: `/api/system/gpu` shows `cuda_available: false`, or jobs fail with `CUDA_UNAVAILABLE`.

- Run `nvidia-smi`
- Confirm PyTorch was installed with a CUDA wheel matching the driver
- If `PROCESSING_DEVICE=auto`, CPU fallback is expected and must be labeled `fallback_reason=CUDA_UNAVAILABLE`
- If `PROCESSING_DEVICE=cuda`, this is a configuration error, not a silent CPU run

## CUDA out of memory

Error code: `CUDA_OUT_OF_MEMORY`.

- Switch to Performance profile
- Lower `INFERENCE_IMAGE_SIZE`
- Keep `INFERENCE_BATCH_SIZE=1` and `MAX_WORKERS=1`
- Close other GPU applications
- Optional `AUTO_FALLBACK_TO_CPU=true` (must appear in UI/logs)

## MODEL_NOT_FOUND

```text
Required model: plate_detector.pt
Expected location: models/plate_detector.pt
Configure PLATE_MODEL_PATH and retry.
```

Same pattern for the vehicle model. Do not expect detections until files exist.

## Video rejected

Codes: `VIDEO_INVALID`, `VIDEO_UNSUPPORTED`, `VIDEO_CORRUPTED`.

- Confirm extension is in `ALLOWED_VIDEO_EXTENSIONS`
- Missing codecs: install a complete OpenCV/FFmpeg build
- Empty or 0-frame files fail validation

## Worker stuck in processing

Stale job recovery should mark abandoned jobs failed after `STALE_JOB_TIMEOUT_SECONDS`. Restart the worker and retry.

## OCR poor on Indian plates

Expected on low-res CCTV, motion blur, and oblique angles. Use Accuracy profile, more observations, and manual verification states. The normalizer will not rewrite `O`→`0` blindly.

## Services will not start

Phase 1 contains layout and docs only. If Compose files are missing, you are not on Phase 2 yet.

## Frontend shows empty metrics

Correct when the database has no jobs. Empty states are intentional; numbers are never faked.
