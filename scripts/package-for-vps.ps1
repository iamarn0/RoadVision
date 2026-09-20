$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$zip = Join-Path ([Environment]::GetFolderPath("Desktop")) "RoadVision-deploy.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }

Push-Location $root
try {
  tar -a -c -f $zip `
    --exclude=node_modules `
    --exclude=.venv `
    --exclude=.venv311 `
    --exclude=.next `
    --exclude=__pycache__ `
    --exclude=.pytest_cache `
    --exclude=storage/uploads `
    --exclude=storage/processed `
    --exclude=storage/evidence `
    --exclude=storage/exports `
    --exclude=.env `
    apps infra packages scripts services models storage docker-compose.yml docker-compose.prod.yml .env.production.example .env.example
}
finally {
  Pop-Location
}

Write-Host "Created $zip"
Write-Host "Upload this file to the VPS. Also copy models\vehicle_detector.pt and models\plate_detector.pt if they were skipped because they are large."
