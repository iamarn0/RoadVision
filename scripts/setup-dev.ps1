# Bootstrap RoadVision for local development on Windows.
# Usage (from repo root):
#   .\scripts\setup-dev.ps1
#   .\scripts\setup-dev.ps1 -DownloadModels
#   .\scripts\setup-dev.ps1 -Python 3.13

param(
    [string]$Python = "3.13",
    [switch]$DownloadModels,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "RoadVision dev setup (Python $Python)" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

# Prefer SQLite for first-run without Postgres (see .env.example).
$envContent = Get-Content ".env" -Raw
if ($envContent -match "DATABASE_URL=postgresql") {
    Write-Host @"
Note: .env uses PostgreSQL. For API-only local dev, switch to:
  DATABASE_URL=sqlite:///./storage/roadvision.db
(or run scripts\setup_postgres.ps1 and keep PostgreSQL)
"@ -ForegroundColor Yellow
}

$venv = Join-Path $Root ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Write-Host "Creating virtual environment at .venv ..."
    & py "-$Python" -m venv $venv
}

$py = Join-Path $venv "Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r "services\api\requirements.txt"
& $py -m pip install -r "services\worker\requirements.txt"

Write-Host "Installing frontend dependencies ..."
Push-Location "apps\web"
npm install --no-audit --no-fund
Pop-Location

if ($DownloadModels) {
    Write-Host "Downloading YOLO model weights (large download) ..."
    & $py "scripts\download_models.py"
}

if (-not $SkipTests) {
    Write-Host "Running test suites ..."
    Push-Location "services\api"
    & $py -m pytest tests -q
    Pop-Location
    Push-Location "services\worker"
    & $py -m pytest tests -q
    Pop-Location
    Push-Location "apps\web"
    npm test
    Pop-Location
}

Write-Host @"

Setup complete.

Activate the venv:
  .\.venv\Scripts\Activate.ps1

Start services (separate terminals; Redis must be running for jobs):

  Terminal 1 — API:
    `$env:PYTHONPATH = "`$PWD;`$PWD\services\api"
    cd services\api
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

  Terminal 2 — worker:
    `$env:PYTHONPATH = "`$PWD;`$PWD\services\worker;`$PWD\services\api"
    cd services\worker
    celery -A app.worker:celery_app worker --loglevel=INFO --concurrency=1 --pool=solo

  Terminal 3 — web:
    cd apps\web
    npm run dev

Open http://localhost:3000 — sign in with BOOTSTRAP_ADMIN_* from .env
API health: http://localhost:8000/health/live

For ANPR jobs, run: py scripts\download_models.py
"@ -ForegroundColor Green
