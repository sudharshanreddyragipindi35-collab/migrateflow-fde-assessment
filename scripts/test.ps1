$ErrorActionPreference = "Stop"
Push-Location backend
python -m ruff check app tests
if ($LASTEXITCODE -ne 0) { throw "Backend lint failed" }
python -m mypy app
if ($LASTEXITCODE -ne 0) { throw "Backend types failed" }
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
Pop-Location
Push-Location frontend
npm run lint
if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed" }
npm test
if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
Pop-Location
python scripts/evaluate.py
if ($LASTEXITCODE -ne 0) { throw "Evaluation failed" }
