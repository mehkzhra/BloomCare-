$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Run the README setup commands first." }
Push-Location (Join-Path $root "backend")
try {
    & $python -m ruff check . ..\scripts
    if ($LASTEXITCODE -ne 0) { throw "Backend lint failed" }
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
    & $python -m alembic current
    if ($LASTEXITCODE -ne 0) { throw "Database migration check failed" }
    & $python -m alembic check
    if ($LASTEXITCODE -ne 0) { throw "Database schema differs from migration" }
} finally { Pop-Location }
Push-Location (Join-Path $root "frontend")
try {
    npm.cmd run lint
    if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed" }
    npm.cmd test
    if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed" }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally { Pop-Location }
Write-Host "All checks passed."
