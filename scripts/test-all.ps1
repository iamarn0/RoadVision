# Run API, worker, and web test suites. Usage: .\scripts\test-all.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "Missing .venv — run .\scripts\setup-dev.ps1 first"
}

Push-Location "services\api"
& $py -m pytest tests -q
Pop-Location

Push-Location "services\worker"
& $py -m pytest tests -q
Pop-Location

Push-Location "apps\web"
npm test
Pop-Location

Write-Host "All test suites passed." -ForegroundColor Green
