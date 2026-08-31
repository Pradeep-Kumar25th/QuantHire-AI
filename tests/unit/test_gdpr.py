"""GDPR stub endpoint tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_gdpr_export_returns_501():
    response = client.post("/api/v1/gdpr/export")
    assert response.status_code in (401, 501)
