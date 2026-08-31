# Pre-deploy gate for Windows — run before ACR push.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> 1. Frontend lib files"
$libFiles = @(
  "api.ts", "api-client.ts", "api-health.ts", "auth-storage.ts",
  "utils.ts", "enterprise-jd-print.ts", "test-connection.ts"
)
foreach ($f in $libFiles) {
  $path = Join-Path "apps\web\src\lib" $f
  if (-not (Test-Path $path)) { throw "Missing $path" }
}

Write-Host "==> 2. Python import check"
$env:PYTHONPATH = "apps/api;apps/agents;apps/agents/agents"
$env:JWT_SECRET_KEY = "test-jwt-secret-key-with-32-chars-minimum"
$env:APP_ENV = "testing"
$env:AUTH_MODE = "none"
python -c "from app.database import engine"

Write-Host "==> 3. Unit tests"
python -m pytest tests/unit -q

Write-Host "==> 4. Frontend build"
Push-Location apps/web
npm ci --legacy-peer-deps
npx tsc --noEmit
npm run build
Pop-Location

Write-Host "==> 5. Docker builds"
docker build -f Dockerfile.backend --target production -t quanthire-backend:predeploy-test .
docker build -f Dockerfile.frontend --target production -t quanthire-frontend:predeploy-test .

Write-Host "`nAll pre-deploy checks passed."
