#!/usr/bin/env bash
# Pre-deploy gate: run locally or in CI before building ACR images.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> 1. Frontend lib tracked and present"
for f in api.ts api-client.ts api-health.ts auth-storage.ts utils.ts enterprise-jd-print.ts test-connection.ts; do
  test -f "apps/web/src/lib/$f" || { echo "MISSING apps/web/src/lib/$f"; exit 1; }
done
if git rev-parse --git-dir >/dev/null 2>&1; then
  git check-ignore -q apps/web/src/lib/api.ts && {
    echo "ERROR: apps/web/src/lib is gitignored"
    exit 1
  }
fi

echo "==> 2. Python syntax (database.py import)"
PYTHONPATH="apps/api:apps/agents:apps/agents/agents" python -c "from app.database import engine"

echo "==> 3. Unit tests"
PYTHONPATH="apps/api:apps/agents:apps/agents/agents" \
  JWT_SECRET_KEY="test-jwt-secret-key-with-32-chars-minimum" \
  APP_ENV=testing AUTH_MODE=none \
  python -m pytest tests/unit -q

echo "==> 4. Frontend typecheck + production build"
cd apps/web
npm ci --legacy-peer-deps
npx tsc --noEmit
npm run build
cd "$ROOT"

echo "==> 5. Production Docker builds"
docker build -f Dockerfile.backend --target production -t quanthire-backend:predeploy-test .
docker build -f Dockerfile.frontend --target production -t quanthire-frontend:predeploy-test .

echo ""
echo "All pre-deploy checks passed. Safe to push to ACR and kubectl apply."
