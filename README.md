# RoadVision

**Vehicle Intelligence & ANPR**

RoadVision is an operational Automatic Number Plate Recognition platform for **uploaded roadside and CCTV video files**. It detects multiple vehicles, tracks them across frames, reads Indian registration plates, aggregates OCR over time, and stores evidence for review and export.

Version: **v0.1.0**

This repository is a greenfield monorepo. Inference uses real models at runtime. The application does not ship fake plates, fake GPU stats, or dummy `.pt` files.

## Features

- Upload and validate video files (MP4, AVI, MOV, MKV, WEBM)
- Background ANPR jobs with real progress from the worker
- Multi-vehicle detection and tracking
- Dedicated plate detection, OCR, conservative Indian plate normalization
- Temporal aggregation, duplicate suppression, confidence states
- Evidence images and annotated output video
- Search, filter, paginated detections, and exports (CSV, XLSX, JSON, evidence ZIP)
- GPU (CUDA) when available, CPU fallback, RTX 3050-aware defaults
- Docker Compose for API, worker, web, PostgreSQL, and Redis

Live cameras (RTSP, webcam, IP) are **not** implemented in v0.1.0. The pipeline consumes a `VideoSource` abstraction so those sources can be added later.

## Architecture

```text
Next.js web  --REST/WebSocket-->  FastAPI API
                                      |
                               PostgreSQL + Redis
                                      |
                                 ANPR worker
                                      |
                                 File storage
```

See [docs/architecture.md](docs/architecture.md).

## Requirements

- Python 3.11+
- Node.js 20+
- PostgreSQL 16
- Redis 7
- NVIDIA driver + CUDA-capable GPU optional (target: RTX 3050 Laptop)
- Vehicle detector and plate detector weights (not committed)

## Installation

1. Copy environment configuration:

   ```bash
   copy .env.example .env
   ```

2. Place models as documented in [models/README.md](models/README.md).

3. Follow [docs/setup.md](docs/setup.md) for Windows local development or Docker.

## GPU setup

Do not install a random CUDA toolkit blindly. Match PyTorch wheels to the installed NVIDIA driver.

```bash
nvidia-smi
```

```python
import torch
print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("CUDA:", torch.version.cuda)
```

Details: [docs/setup.md](docs/setup.md) and [docs/troubleshooting.md](docs/troubleshooting.md).

## Model setup

Required:

- `models/vehicle_detector.pt`
- `models/plate_detector.pt`

If a model is missing, jobs fail with `MODEL_NOT_FOUND`. They do not invent detections.

## Environment configuration

All secrets and runtime paths come from `.env`. Template: `.env.example`.

Defaults for laptop GPUs:

- `MAX_WORKERS=1`
- `INFERENCE_BATCH_SIZE=1`
- `PROCESSING_DEVICE=auto`

## Running locally

See [docs/setup.md](docs/setup.md). High-level:

1. Start PostgreSQL and Redis
2. Run API (`services/api`)
3. Run worker (`services/worker`)
4. Run web (`apps/web`)

## Docker

```bash
docker compose up --build
```

GPU in Docker is optional (`infra/docker` compose profiles). CPU mode remains supported.

## Processing a video

1. Open the web app → Upload
2. Select a roadside video
3. Create a processing job
4. Watch real worker progress
5. Review annotated video, unique plates, and evidence
6. Export results

## Testing

```bash
make api-test
make worker-test
```

Frontend tests live under `apps/web`. Mocks are allowed in tests only.

## Troubleshooting

[docs/troubleshooting.md](docs/troubleshooting.md)

## Deployment

[docs/deployment.md](docs/deployment.md)

## Authentication

RoadVision uses **httpOnly session cookies** and admin-provisioned accounts (no public registration).

1. Set `AUTH_DISABLED=false` (required in production).
2. Set a strong `SECRET_KEY`.
3. Set `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` for the first admin (created only when the user table is empty).
4. Sign in at `/login`. Admins manage users under **Users**.

Roles: `admin` (full access + user management), `operator` (upload/process/export), `auditor` (read-only).

`AUTH_DISABLED=true` is allowed only for automated tests and local emergency debugging — never in `APP_ENV=production`.

## Limitations (v0.1.0)

- Uploaded files only (no live CCTV)
- Single worker recommended on RTX 3050-class laptops
- OCR quality depends on resolution, blur, and lighting
- Plate detector must be a dedicated model, not a vehicle-class detector

## Future roadmap

- RTSP / IP camera / webcam `VideoSource` implementations
- Multi-camera management
- Stronger authentication providers
- Operator workflows for manual verification queues

## Documentation

- [Architecture](docs/architecture.md)
- [Setup](docs/setup.md)
- [AI pipeline](docs/ai-pipeline.md)
- [API](docs/api.md)
- [Security](docs/security.md)
- [Deployment](docs/deployment.md)
- [Troubleshooting](docs/troubleshooting.md)
