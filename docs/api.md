# API

FastAPI generates OpenAPI at `/docs` when the API service is running (disabled when `APP_ENV=production`). This file is the human index for RoadVision v0.1.0.

## Authentication

Session cookie auth (httpOnly). Send credentials with browser `fetch` (`credentials: "include"`).

| Method | Path | Access |
| --- | --- | --- |
| POST | `/api/auth/login` | public (rate-limited) |
| POST | `/api/auth/logout` | authenticated |
| GET | `/api/auth/me` | authenticated |
| POST | `/api/auth/change-password` | authenticated |
| GET / POST | `/api/users` | admin (Personnel) |
| PATCH | `/api/users/{id}` | admin |
| POST | `/api/users/{id}/reset-password` | admin |
| POST | `/api/users/{id}/revoke-sessions` | admin |

Issuing access returns the initial `temporary_password` once for the administrator to share.

With `AUTH_DISABLED=true` (tests only), requests act as a synthetic admin. Production refuses that flag.

Error envelope:

```json
{
  "error_code": "VIDEO_INVALID",
  "message": "The uploaded file is not a readable video.",
  "details": {}
}
```

Do not return stack traces to clients.

## Health

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| GET | `/health/live` | Process is up | public |
| GET | `/api/version` | Product version, short commit, environment | public |
| GET | `/health/ready` | Database, Redis, storage reachable | authenticated |
| GET | `/metrics` | Operational counters | authenticated |

## System

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/system/gpu` | Runtime CUDA/device facts |
| GET | `/api/system/health` | Hardware, AI models, infra, performance |

GPU payload fields are detected at runtime: `cuda_available`, `device`, `gpu_name`, memory, Torch/CUDA versions, `fp16_enabled`, `status`.

## Videos

| Method | Path | Roles |
| --- | --- | --- |
| POST | `/api/videos/upload` | admin, operator |
| GET | `/api/videos` | admin, operator, auditor |
| GET | `/api/videos/{video_id}` | admin, operator, auditor |
| DELETE | `/api/videos/{video_id}` | admin |

Upload validates extension, MIME, size, and decodability. Storage keys are opaque; filesystem paths are never returned.

## Jobs

| Method | Path | Roles |
| --- | --- | --- |
| POST | `/api/videos/{video_id}/process` | admin, operator |
| GET | `/api/jobs` | readers |
| GET | `/api/jobs/{job_id}` | readers |
| POST | `/api/jobs/{job_id}/cancel` | admin, operator |
| POST | `/api/jobs/{job_id}/retry` | admin, operator |

## Results

| Method | Path |
| --- | --- |
| GET | `/api/jobs/{job_id}/results` |
| GET | `/api/jobs/{job_id}/observations` |
| GET | `/api/plate-detections/{detection_id}` |
| GET | `/api/detections` |

Results are paginated. Observations are a separate, paged resource.

## Exports

| Method | Path | Roles |
| --- | --- | --- |
| POST | `/api/jobs/{job_id}/exports/csv` | admin, operator |
| POST | `/api/jobs/{job_id}/exports/xlsx` | admin, operator |
| POST | `/api/jobs/{job_id}/exports/json` | admin, operator |
| POST | `/api/jobs/{job_id}/exports/evidence-zip` | admin, operator |
| GET | `/api/exports/{export_id}` | readers |

## Media

| Method | Path |
| --- | --- |
| GET | `/api/media/{asset_id}` |

Media access requires the same session boundary as JSON APIs.

## Real-time updates

WebSocket `/ws/jobs/{job_id}` requires a valid session cookie. Prefer WS or poll `GET /api/jobs/{job_id}`.

Progress event schema: `packages/contracts/event-schemas/job-progress.json`.
