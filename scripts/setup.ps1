$ErrorActionPreference = "Stop"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m pip install -e "backend[dev]"
if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed" }
Push-Location frontend
npm ci
if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed" }
Pop-Location
Write-Host "MigrateFlow dependencies installed."
