"""Production Dockerfile invariants for ACR builds."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "Dockerfile.backend"
FRONTEND = REPO / "Dockerfile.frontend"


def test_backend_dockerfile_enables_quantchat_import():
    content = BACKEND.read_text(encoding="utf-8")
    assert "COPY apps/quantchat /srv/apps/quantchat" in content
    assert "touch /srv/apps/__init__.py" in content
    assert "requirements.linux.txt" in content


def test_frontend_dockerfile_has_public_and_healthcheck():
    content = FRONTEND.read_text(encoding="utf-8")
    assert "mkdir -p public" in content
    assert "/api/health" in content
    assert "COPY apps/web" in content
    assert "npm ci --legacy-peer-deps" in content
    assert 'CMD ["node", "server.js"]' in content
