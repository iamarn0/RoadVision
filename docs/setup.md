# Setup

RoadVision v0.1.0 local setup. Two paths: Windows native (recommended for GPU on a laptop) and Docker (CPU by default, optional GPU profile).

## Prerequisites

- Windows 10/11
- Python 3.11+
- Node.js 20+
- Git
- PostgreSQL 16 and Redis 7 (native or Docker)
- NVIDIA driver if using CUDA

## Environment variables

```powershell
copy .env.example .env
```

Change `SECRET_KEY` and database passwords. Do not commit `.env`.

## NVIDIA driver verification

```powershell
nvidia-smi
```

Note the driver version and CUDA version reported by the driver. Install a **matching PyTorch wheel**; do not assume a CUDA toolkit version.

## PyTorch CUDA verification

After installing PyTorch into the worker environment:

```python
import torch

print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("CUDA:", torch.version.cuda)
```

`PROCESSING_DEVICE=auto` uses CUDA when `torch.cuda.is_available()` is true. `cuda` mode fails with `CUDA_UNAVAILABLE` if it is not. `cpu` always uses CPU.

## Model installation

See [models/README.md](../models/README.md). Place:

- `models/vehicle_detector.pt`
- `models/plate_detector.pt`

## Windows local development

### 1. Python

Create a healthy virtual environment (do not reuse a broken leftover `.venv`):

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r services\api\requirements.txt
pip install -r services\worker\requirements.txt
```

For CUDA on RTX 3050-class laptops, install a matching PyTorch wheel **before** ultralytics:

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

Adjust the CUDA index to match `nvidia-smi`.

### 2. Node.js

```powershell
cd apps\web
npm install
```

### 3. PostgreSQL / Redis

Install locally, or after Docker Desktop is available:

```powershell
docker compose up postgres redis -d
```

Apply migrations from the repo root with PYTHONPATH including the monorepo root:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\services\api"
cd services\api
alembic upgrade head
cd ..\..
```

### 4. Run API

```powershell
$env:PYTHONPATH = "$PWD;$PWD\services\api"
cd services\api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Run worker

```powershell
$env:PYTHONPATH = "$PWD;$PWD\services\worker;$PWD\services\api"
cd services\worker
celery -A app.worker:celery_app worker --loglevel=INFO --concurrency=1 --pool=solo
```

On Windows, `--pool=solo` avoids billiard issues.

### 6. Run frontend

```powershell
cd apps\web
npm run dev
```

Open `http://localhost:3000` and sign in at `/login`.

Configure bootstrap admin in `.env`:

```text
AUTH_DISABLED=false
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=change-me-bootstrap
```

The first API startup creates that admin when the user table is empty. Sign in at `/login`. Additional personnel are issued from **Personnel** in the console.

### 3. PostgreSQL / Redis

Either install locally or start only data services:

```powershell
docker compose up postgres redis
```

Apply migrations:

```powershell
cd services\api
alembic upgrade head
```

### 4. Run API

```powershell
cd services\api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Run worker

```powershell
cd services\worker
celery -A app.worker worker --loglevel=INFO --concurrency=1
```

### 6. Run frontend

```powershell
cd apps\web
npm run dev
```

Open `http://localhost:3000` and sign in.

## Docker

```powershell
docker compose up --build
```

GPU worker profile (optional, NVIDIA Container Toolkit required):

```powershell
docker compose --profile gpu up --build
```

Docker GPU is **not** required. CPU containers must still start.

## First video

1. Confirm `/health/live` on the API
2. Sign in and open System Health / GPU
3. Upload a short MP4
4. Start a job only after models exist

## Phase status

v0.1.0 application code for API, worker, and web is implemented for uploaded-video ANPR with session authentication and RBAC.

Manual prerequisites before processing a video:

1. PostgreSQL + Redis running (or SQLite for local API-only work)
2. `alembic upgrade head`
3. Model weights in `models/` (see [models/README.md](../models/README.md))
4. Bootstrap admin env vars set
5. Optional CUDA PyTorch wheel matching `nvidia-smi`

Docker Compose is provided but not required. On this development machine Docker may be absent; use native Windows services.
