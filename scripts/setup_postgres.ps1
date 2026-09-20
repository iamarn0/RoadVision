# Creates RoadVision Postgres role + database.
# Usage (from repo root):
#   .\scripts\setup_postgres.ps1 -PostgresPassword "YOUR_POSTGRES_PASSWORD"
#
# Optional:
#   .\scripts\setup_postgres.ps1 -PostgresPassword "..." -AppPassword "change-me"

param(
    [Parameter(Mandatory = $true)]
    [string]$PostgresPassword,

    [string]$PostgresUser = "postgres",
    [string]$AppUser = "roadvision",
    [string]$AppPassword = "change-me",
    [string]$AppDb = "roadvision",
    [string]$HostName = "localhost",
    [int]$Port = 5432
)

$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
if (-not (Test-Path $psql)) {
    throw "psql not found at $psql"
}

$env:PGPASSWORD = $PostgresPassword

$sql = @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$AppUser') THEN
    CREATE ROLE $AppUser LOGIN PASSWORD '$AppPassword';
  ELSE
    ALTER ROLE $AppUser WITH LOGIN PASSWORD '$AppPassword';
  END IF;
END
`$`$;
SELECT 'role_ready' AS status;
"@

& $psql -U $PostgresUser -h $HostName -p $Port -d postgres -v ON_ERROR_STOP=1 -c $sql
if ($LASTEXITCODE -ne 0) { throw "Failed to create/update role $AppUser" }

$dbExists = & $psql -U $PostgresUser -h $HostName -p $Port -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$AppDb'"
if ($dbExists.Trim() -ne "1") {
    & $psql -U $PostgresUser -h $HostName -p $Port -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $AppDb OWNER $AppUser;"
    if ($LASTEXITCODE -ne 0) { throw "Failed to create database $AppDb" }
}

& $psql -U $PostgresUser -h $HostName -p $Port -d $AppDb -v ON_ERROR_STOP=1 -c "GRANT ALL ON SCHEMA public TO $AppUser; ALTER SCHEMA public OWNER TO $AppUser;"
if ($LASTEXITCODE -ne 0) { throw "Failed to grant schema permissions" }

Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
Write-Host "Postgres ready: user=$AppUser db=$AppDb"
Write-Host "Next: cd services\api; py -3 -m alembic upgrade head"
