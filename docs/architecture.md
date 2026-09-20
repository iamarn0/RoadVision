# Architecture

RoadVision is a service-oriented ANPR platform. v0.1.0 processes **uploaded video files** only.

## Service map

```text
                    ┌─────────────────────┐
                    │     Next.js Web      │
                    │   Professional UI    │
                    └──────────┬──────────┘
                               │
                         REST / WebSocket
                               │
                    ┌──────────▼──────────┐
                    │     FastAPI API     │
                    └───────┬───────┬─────┘
                            │       │
                       PostgreSQL   Redis
                            │       │
                    ┌───────▼───────▼─────┐
                    │   ANPR AI Worker    │
                    └──────────┬──────────┘
                               │
                         File Storage
```

## Responsibilities

| Component | Role |
| --- | --- |
| `apps/web` | Operational UI: upload, jobs, results, health, settings |
| `services/api` | Auth-ready HTTP API, validation, persistence, job enqueue, media access |
| `services/worker` | Frame pipeline, GPU/CPU inference, evidence, annotated video |
| PostgreSQL | Canonical records: videos, jobs, tracks, detections, observations, assets, audit |
| Redis | Celery broker, job progress pub/sub, rate-limit counters |
| Storage | Original video, processed video, evidence, exports |

## Design decisions

1. **Split API and worker** so inference load does not block HTTP.
2. **Repository + service layers** in the API; pipeline interfaces in the worker.
3. **`VideoSource` abstraction** with `UploadedFileSource` now; RTSP/webcam later without rewriting ANPR stages.
4. **`source_id` + `source_type`** on videos/jobs so multi-camera is additive.
5. **No fake inference.** Missing models and CUDA failures are first-class error codes.
6. **One worker / batch size 1** by default for RTX 3050-class VRAM.
7. **Unique detections vs raw observations** so the UI never dumps every frame.

## ANPR pipeline (worker)

```text
VideoSource.read()
  → VehicleDetector
  → VehicleTracker
  → PlateDetector (interval)
  → spatial association
  → PlatePreprocessor
  → OCREngine (interval + quality gate)
  → PlateNormalizer
  → ObservationAggregator
  → DuplicateSuppressor
  → EvidenceGenerator
  → AnnotatedVideoRenderer
  → persist results
```

## Job lifecycle

`queued → validating → processing → finalizing → completed`

Failure and cancel states: `failed`, `cancelled`. Upload uses video `status` independently.

Each processing **run** has a unique id. Retry deletes or supersedes prior run artifacts for that job so unique detections are not duplicated.

Stale `processing` jobs are recovered after `STALE_JOB_TIMEOUT_SECONDS`.

## Contracts

Shared TypeScript types live in `packages/contracts/api-types`. Job progress events live in `packages/contracts/event-schemas`.

## Versioning

Application version: `0.1.0` (`APP_VERSION`). Each job stores detector versions, OCR engine, device, and processing profile.
